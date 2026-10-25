FROM --platform=linux/amd64 ros:humble-ros-base
SHELL ["/bin/bash", "-c"]
ARG BUILD_JOBS=2
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git ca-certificates libboost-all-dev libeigen3-dev \
    libtbb-dev libopencv-dev python3-pip python3-colcon-common-extensions \
    python3-numpy python3-opencv python3-psutil \
    ros-humble-cv-bridge ros-humble-rtabmap-odom ros-humble-rtabmap-msgs \
    ros-humble-rtabmap-conversions ros-humble-rtabmap ros-humble-nav2-msgs \
    ros-humble-perception-pcl ros-humble-laser-geometry ros-humble-tf2-eigen \
    ros-humble-tf2-geometry-msgs ros-humble-image-geometry ros-humble-rosgraph-msgs \
    ros-humble-diagnostic-msgs ros-humble-rviz-common ros-humble-rviz-rendering \
    ros-humble-message-filters && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir numpy==1.26.4 \
    && python3 -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
       torch==2.2.2 torchvision==0.17.2 \
    && python3 -m pip install --no-cache-dir networkx==3.2.1 numba==0.59.1 \
       Pillow==10.3.0 scikit-learn==1.4.2 scipy==1.11.4 sortedcontainers==2.4.0 distinctipy==1.3.4
COPY sources/workspace/gtsam /opt/gtsam
RUN cmake -S /opt/gtsam -B /opt/gtsam/build -DCMAKE_BUILD_TYPE=Release \
      -DGTSAM_BUILD_TESTS=OFF -DGTSAM_BUILD_EXAMPLES_ALWAYS=OFF \
      -DGTSAM_BUILD_UNSTABLE=OFF -DGTSAM_BUILD_WITH_MARCH_NATIVE=OFF \
      -DGTSAM_USE_SYSTEM_EIGEN=ON -DGTSAM_WITH_TBB=OFF \
    && cmake --build /opt/gtsam/build -j"$BUILD_JOBS" \
    && cmake --install /opt/gtsam/build && ldconfig
COPY sources/upstream /opt/source-original/index
COPY sources/workspace/cslam /opt/source-original/cslam
COPY sources/workspace/cslam_interfaces /opt/source-original/cslam_interfaces
COPY sources/workspace/cslam_experiments /opt/source-original/cslam_experiments
COPY native /opt/adapter
RUN mkdir -p /opt/ws/src && cp -a /opt/source-original/cslam /opt/ws/src/ \
    && cp -a /opt/source-original/cslam_interfaces /opt/ws/src/ \
    && cp -a /opt/source-original/cslam_experiments /opt/ws/src/ \
    && python3 /opt/adapter/patch_build.py /opt/ws/src/cslam
COPY assets/ResNet18_64_cosplace.pth /opt/ws/src/cslam/models/resnet18_64.pth
WORKDIR /opt/ws
RUN source /opt/ros/humble/setup.bash \
    && MAKEFLAGS="-j$BUILD_JOBS" colcon build --executor sequential \
       --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
COPY runtime /opt/ab3
ENV ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=42 PYTHONUNBUFFERED=1
ENTRYPOINT ["/bin/bash", "/opt/ab3/entrypoint_ros2.sh"]
