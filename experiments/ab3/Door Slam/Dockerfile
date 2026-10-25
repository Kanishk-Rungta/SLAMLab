# Native historical ROS 1 stack. No lidar/RangeFinder/GPS/DJI drivers launched.
FROM --platform=linux/amd64 ros:melodic-perception
SHELL ["/bin/bash", "-c"]
ARG BUILD_JOBS=1
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git pkg-config python3 python-pip python-catkin-tools \
    python-numpy python-scipy python-opencv python-psutil unzip ca-certificates \
    libboost-all-dev libtbb-dev libeigen3-dev libmetis-dev libopenni2-dev \
    libpcl-dev libopencv-dev libqt5svg5-dev qtbase5-dev \
    ros-melodic-cv-bridge ros-melodic-image-transport ros-melodic-tf-conversions \
    ros-melodic-eigen-conversions ros-melodic-tf2-ros ros-melodic-nav-msgs \
    ros-melodic-message-generation ros-melodic-rosgraph-msgs \
    ros-melodic-find-object-2d ros-melodic-costmap-2d ros-melodic-octomap-msgs \
    ros-melodic-move-base-msgs ros-melodic-rviz ros-melodic-laser-geometry \
    ros-melodic-image-geometry ros-melodic-pcl-ros \
    && rm -rf /var/lib/apt/lists/*
RUN python2 -m pip install --no-cache-dir 'pip==20.3.4' \
    && python2 -m pip install --no-cache-dir 'setuptools<45' 'wheel<0.35' \
    && python2 -m pip install --no-cache-dir 'numpy==1.16.6' \
    && python2 -m pip install --no-cache-dir \
       'https://files.pythonhosted.org/packages/ec/98/f968caf5f65759e78873b900cbf0ae20b1699fb11268ecc0f892186419a7/tensorflow-1.15.0-cp27-cp27mu-manylinux2010_x86_64.whl'
# Match the dependencies of the official ROS frontend without substituting the
# packaged rtabmap_ros executable for the author's pinned custom fork.
RUN apt-get update && apt-get install -y --no-install-recommends \
    $(apt-cache depends ros-melodic-rtabmap-ros | awk '/Depends:/{print $2}' | grep -v '^<') \
    && rm -rf /var/lib/apt/lists/*
COPY config /opt/benchmark/config
COPY native /opt/benchmark/native
COPY bridge /opt/benchmark/bridge
COPY tools/patch_runtime.py /opt/benchmark/tools/patch_runtime.py
COPY source_lock.json /opt/benchmark/source_lock.json
COPY algorithm/DOOR-SLAM-original.zip /opt/benchmark/DOOR-SLAM-original.zip
RUN python3 /opt/benchmark/native/extract_original.py
RUN python3 /opt/benchmark/native/build_dependencies.py
# Build copies get the explicit I/O/telemetry patches; the original is retained.
RUN cp -a /opt/source-original /opt/source \
    && python3 /opt/benchmark/tools/patch_runtime.py /opt/source
RUN bash /opt/benchmark/native/build_native.sh
ENV PYTHONPATH=/opt/deps/netvlad/python
COPY native/entrypoint.sh /opt/benchmark/entrypoint.sh
RUN chmod +x /opt/benchmark/entrypoint.sh
ENTRYPOINT ["/opt/benchmark/entrypoint.sh"]
