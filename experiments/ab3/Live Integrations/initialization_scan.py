"""DVM benchmark motion before its first native tracked pose; no pose estimation."""
import math

SETTLE_SECONDS = 2.
ANGULAR_SPEED = .25  # rad/s; slower than the normal reactive turn rate
SCAN_SECONDS = 2 * math.pi / ANGULAR_SPEED
REACTIVE_SECONDS = 10.


def scan_command(now, robot_number, initialized, stereo_age):
    """Request an in-place scan, or leave the normal reactive policy in charge.

    After settling, command one full turn, then allow ten seconds of reactive
    movement to change the view. Repeat until a genuine native pose is received.
    This is commanded rotation, not a measured heading or map-completion claim.
    """
    if initialized or now < SETTLE_SECONDS or not 0. <= stereo_age < .5:
        return None
    phase = (now - SETTLE_SECONDS) % (SCAN_SECONDS + REACTIVE_SECONDS)
    if phase >= SCAN_SECONDS:
        return None
    return 0., ANGULAR_SPEED * (1 if robot_number % 2 else -1)
