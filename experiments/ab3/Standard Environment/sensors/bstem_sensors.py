"""Standard sensor and actuator interface of the benchmark robot (robot/robot_spec.json).

Every algorithm reads its sensors and drives through this class, so all of them see exactly the same
measurements, errors and radio. It injects the hardware-like errors from the spec (unknown to the
algorithms) with a fixed random stream per robot (seed + 100 * robot number):
  wheels  per-wheel radius error, slip per metre, encoder noise
  gyro    3 axes (L3GD20). White noise, constant bias, bias random walk, scale-factor error per
          axis. The rate is the true rotation over each control step / dt: what a continuously
          filtered MEMS gyro reports. (Webots' Gyro returns one instantaneous physics sample, which
          aliases contact jitter.) read() gives the yaw rate; imu() adds the roll/pitch rates. The
          x/y axes use their own random stream, so the yaw-rate stream is unchanged by them.
  camera  image noise and frame dropouts
  radio   loss, delay and a per-robot bandwidth limit
A benchmark noise scenario ($SLAM_BENCH_SCENARIO, "noise_scale") multiplies the noise terms.

    sensors = BstemSensors(robot)                 # robot = controller.Robot / Supervisor
    while robot.step(sensors.step_ms) != -1:
        wheel_m, gyro_z, accel = sensors.read()   # wheel travel (m) since last call, yaw rate (rad/s)
        gyro_xyz, accel = sensors.imu()           # optional, after read(): 3-axis body rates (rad/s)
        frame = sensors.images()                  # (left, right) BGR uint8 or None
        for packet in sensors.receive(): ...
        sensors.send(packet)
        sensors.drive(linear_m_s, angular_rad_s)
"""
import json
import math
import os
import re
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_PATH = os.path.join(HERE, '..', 'robot', 'robot_spec.json')


def load_spec(path=SPEC_PATH):
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


def scenario_noise_scale():
    path = os.environ.get('SLAM_BENCH_SCENARIO')
    if path and os.path.exists(path):
        with open(path, encoding='utf-8-sig') as f:
            return float(json.load(f).get('noise_scale', 1.))
    return 1.


class BstemSensors(object):
    def __init__(self, robot, spec=None):
        self.robot = robot
        self.spec = spec or load_spec()
        s, e = self.spec, self.spec['sensor_errors']
        self.step_ms = int(s['timing']['control_step_ms'])
        if self.step_ms % int(robot.getBasicTimeStep()):
            raise ValueError('control step must be a multiple of the world basicTimeStep')
        self.dt = self.step_ms/1000.
        match = re.search(r'(\d+)$', robot.getName())
        self.number = int(match.group(1)) if match else 1
        self.rng = np.random.RandomState(e['seed']+100*self.number)
        self.noise = scenario_noise_scale()
        d = s['drive']
        self.wheel_radius, self.track = d['wheel_radius_m'], d['track_width_m']
        self.max_wheel = d['max_wheel_speed_rad_s']
        self.motors = [robot.getDevice(n) for n in d['motors']]
        for m in self.motors:
            m.setPosition(float('inf'))
            m.setVelocity(0.)
        self.encoders = [robot.getDevice(n) for n in d['encoders']]
        self.accel = robot.getDevice(s['imu']['accelerometer'])
        self.attitude = robot.getDevice('sim_attitude')      # simulation-only, for the gyro model
        for dev in self.encoders+[self.accel, self.attitude]:
            dev.enable(self.step_ms)
        self.radius_scale = 1+e['wheel_radius_error']*self.rng.uniform(-1, 1, 2)
        self.gyro_scale = 1+e['gyro_scale_error']*self.rng.choice([-1., 1.])
        self.bias = e['gyro_bias_rad_s']
        self.previous = None
        self.last_yaw = None
        # Roll/pitch axes: an independent stream (seed + 100 n + 50), so adding them leaves every
        # earlier measurement (wheels, yaw rate, images, radio) bit-identical.
        self.rng_xy = np.random.RandomState(e['seed']+100*self.number+50)
        self.gyro_scale_xy = 1+e['gyro_scale_error']*self.rng_xy.choice([-1., 1.], 2)
        self.bias_xy = e['gyro_bias_rad_s']*self.rng_xy.choice([-1., 1.], 2)
        self.last_rotation = None
        self.last_gyro = 0.
        self.last_accel = np.zeros(3)
        self.imu_tick = -1
        st = s['stereo']
        self.cameras = [robot.getDevice(n) for n in st['device_names']]
        self.camera_ticks = int(math.ceil(s['timing']['camera_period_ms']/self.step_ms))
        for cam in self.cameras:
            if (cam.getWidth(), cam.getHeight()) != (st['width'], st['height']) or abs(cam.getFov()-st['hfov_rad']) > 1e-4:
                raise RuntimeError('World camera does not match the standard robot spec')
            cam.enable(self.camera_ticks*self.step_ms)
        r = s['radio']
        self.emitter, self.receiver = robot.getDevice(r['emitter']), robot.getDevice(r['receiver'])
        self.emitter.setChannel(r['channel'])
        self.receiver.setChannel(r['channel'])
        self.receiver.enable(self.step_ms)
        self.radio = r
        self.outbox = []
        self.credit = float(r['bandwidth_limit_Bps'])
        self.last_send_time = 0.
        self.dropped_bandwidth = 0
        self.tick = 0

    # ---- proprioception ---------------------------------------------------------------------
    def read(self):
        """(wheel travel [left, right] in m since the previous call, gyro yaw rate rad/s, accel xyz)."""
        e = self.spec['sensor_errors']
        self.tick += 1
        angles = np.array([enc.getValue() for enc in self.encoders])
        if self.previous is None:
            delta = np.zeros(2)
        else:
            delta = (angles-self.previous)*self.wheel_radius*self.radius_scale
            delta += self.rng.normal(0, e['slip_per_m']*self.noise*abs(float(np.mean(delta))))
        self.previous = angles
        delta += self.rng.normal(0, e['encoder_std_m']*self.noise, 2)
        yaw = self.attitude.getRollPitchYaw()[2]
        rate = 0. if self.last_yaw is None else math.atan2(math.sin(yaw-self.last_yaw), math.cos(yaw-self.last_yaw))/self.dt
        self.last_yaw = yaw
        self.bias += self.rng.normal(0, e['gyro_bias_walk_rad_s_per_sqrt_s']*math.sqrt(self.dt))
        gyro = rate*self.gyro_scale+self.bias+self.rng.normal(0, e['gyro_std_rad_s']*self.noise)
        self.last_gyro = float(gyro)
        self.last_accel = np.asarray(self.accel.getValues(), float)
        return delta, float(gyro), self.last_accel

    @staticmethod
    def _rotation(roll, pitch, yaw):
        cr, sr, cp, sp, cy, sy = (math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch),
                                  math.cos(yaw), math.sin(yaw))
        return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                         [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
                         [-sp, cp*sr, cp*cr]])

    def imu(self):
        """(gyro [x, y, z] rad/s in the body frame, accelerometer [x, y, z] m/s2), for this step.

        Call once per step, after read(). z is exactly read()'s yaw rate; x and y are the roll and
        pitch body rates (true rotation over the step / dt) with the same error model as z."""
        e = self.spec['sensor_errors']
        if self.imu_tick == self.tick:
            raise RuntimeError('imu() must be called at most once per step, after read()')
        self.imu_tick = self.tick
        rotation = self._rotation(*self.attitude.getRollPitchYaw())
        if self.last_rotation is None:
            rates = np.zeros(2)
        else:
            relative = self.last_rotation.T.dot(rotation)          # body-frame rotation over the step
            angle = math.acos(max(-1., min(1., (np.trace(relative)-1)/2)))
            axis = np.array([relative[2, 1]-relative[1, 2], relative[0, 2]-relative[2, 0], relative[1, 0]-relative[0, 1]])
            vector = axis*(angle/(2*math.sin(angle)) if angle > 1e-9 else .5)
            rates = vector[:2]/self.dt
        self.last_rotation = rotation
        self.bias_xy = self.bias_xy+self.rng_xy.normal(0, e['gyro_bias_walk_rad_s_per_sqrt_s']*math.sqrt(self.dt), 2)
        xy = rates*self.gyro_scale_xy+self.bias_xy+self.rng_xy.normal(0, e['gyro_std_rad_s']*self.noise, 2)
        return np.array([xy[0], xy[1], self.last_gyro]), self.last_accel.copy()

    # ---- cameras ----------------------------------------------------------------------------
    def images(self):
        """(left, right) BGR uint8 images at the camera period (None in between and on dropouts)."""
        e = self.spec['sensor_errors']
        if self.tick % self.camera_ticks or self.rng.rand() < e['camera_dropout']:
            return None
        out = []
        for cam in self.cameras:
            raw = cam.getImage()
            if raw is None:
                return None
            img = np.frombuffer(raw, np.uint8).reshape(cam.getHeight(), cam.getWidth(), 4)[:, :, :3]
            noise = self.rng.normal(0, e['image_noise_std']*self.noise, img.shape)
            out.append(np.clip(img.astype(float)+noise, 0, 255).astype(np.uint8))
        return out

    # ---- actuation ----------------------------------------------------------------------------
    def drive(self, linear, angular):
        speeds = np.array([(linear-angular*self.track/2)/self.wheel_radius, (linear+angular*self.track/2)/self.wheel_radius])
        scale = max(1., float(np.max(np.abs(speeds)))/self.max_wheel)
        for motor, speed in zip(self.motors, speeds/scale):
            motor.setVelocity(float(speed))

    # ---- radio --------------------------------------------------------------------------------
    def send(self, packet):
        """Broadcast bytes. Beyond the bandwidth limit the packet is dropped; otherwise it may be lost
        (loss_rate) or delayed (delay_s) before transmission."""
        now = self.robot.getTime()
        self.credit = min(self.radio['bandwidth_limit_Bps'], self.credit+(now-self.last_send_time)*self.radio['bandwidth_limit_Bps'])
        self.last_send_time = now
        if len(packet) > self.credit:
            self.dropped_bandwidth += 1
            return False
        self.credit -= len(packet)
        if self.rng.rand() < self.radio['loss_rate']*min(self.noise, 10.):
            return True                   # lost in the air
        lo, hi = self.radio['delay_s']
        self.outbox.append((now+self.rng.uniform(lo, hi), bytes(packet)))
        self.flush()
        return True

    def flush(self):
        now = self.robot.getTime()
        due = [p for p in self.outbox if p[0] <= now]
        self.outbox = [p for p in self.outbox if p[0] > now]
        for _, packet in due:
            self.emitter.send(packet)

    def receive(self):
        self.flush()
        packets = []
        while self.receiver.getQueueLength() and len(packets) < 256:
            packets.append(bytes(self.receiver.getBytes()))
            self.receiver.nextPacket()
        return packets
