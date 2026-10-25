# Original Kimera-Multi (MIT-SPARK, pinned in source_lock.json and algorithm/workspace/*.lock.json).
# Follows upstream docker/Dockerfile (ROS Noetic, dependencies, catkin config, the two upstream patches,
# vocabulary download) with the workspace taken from the locked local copies instead of vcs import.
# Differences, all documented in SOURCE_AND_ADAPTERS.md:
#   * opengv_catkin: upstream's nathanhhughes/opengv_catkin@fix/march_native_optional no longer exists
#     (HTTP 404). MIT-SPARK/opengv_catkin @ b2cf789 (same option OPENGV_BUILD_WITH_MARCH_NATIVE, which
#     the upstream build sets OFF) is used instead.
#   * added package ab3_kimera_adapter (launch copy with AB3 params/topics + output node).
FROM --platform=linux/amd64 ros:noetic
SHELL ["/bin/bash", "-c"]
ARG BUILD_JOBS=2
ENV DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC WORKSPACE=/root/catkin_ws CATKIN_WS=/root/catkin_ws
RUN apt-get update && apt-get install -q -y --no-install-recommends \
      apt-utils git cmake build-essential unzip pkg-config autoconf libtool wget patch \
      libboost-all-dev libjpeg-dev libpng-dev libtiff-dev libvtk6-dev libgtk-3-dev libgtk2.0-dev \
      libatlas-base-dev gfortran libparmetis-dev libtbb-dev libgflags-dev libgoogle-glog-dev \
      libsuitesparse-dev protobuf-compiler opencl-headers ocl-icd-opencl-dev opencl-clhpp-headers \
      python3-wstool python3-catkin-tools python3-pip python3-psutil python3-numpy \
      ros-noetic-desktop-full ros-noetic-image-geometry ros-noetic-pcl-ros ros-noetic-cv-bridge \
      ros-noetic-cmake-modules ros-noetic-tf-conversions ros-noetic-camera-info-manager \
      ros-noetic-interactive-markers ros-noetic-ompl \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir 'empy==3.3.4' catkin_pkg gdown
RUN mkdir -p $WORKSPACE/src
COPY sources/workspace $WORKSPACE/src
COPY sources/upstream $WORKSPACE/src/kimera_multi
RUN git clone https://github.com/MIT-SPARK/opengv_catkin.git $WORKSPACE/src/opengv_catkin \
    && git -C $WORKSPACE/src/opengv_catkin checkout b2cf789eb1dff2cc57ac65c8919cb8030807f4c5
# Upstream patches (docker/copy/*.patch); the locked copies are not git checkouts, so use patch(1).
RUN cd $WORKSPACE/src/kimera_multi_lcd && patch -p1 < $WORKSPACE/src/kimera_multi/docker/copy/kimera_multi_lcd.patch \
    && cd $WORKSPACE/src/kimera_semantics && patch -p1 < $WORKSPACE/src/kimera_multi/docker/copy/kimera_semantics.patch
WORKDIR $WORKSPACE
RUN catkin init \
    && catkin config -a --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo -DGTSAM_TANGENT_PREINTEGRATION=OFF \
         -DGTSAM_BUILD_WITH_MARCH_NATIVE=OFF -DOPENGV_BUILD_WITH_MARCH_NATIVE=OFF \
    && catkin config --merge-devel \
    && source /opt/ros/noetic/setup.bash && catkin build -c -s -j"$BUILD_JOBS"
# Vocabulary (upstream docker downloads it from Google Drive); checksum recorded for provenance.
RUN cd $WORKSPACE/src/kimera_multi_lcd \
    && gdown 'https://drive.google.com/uc?export=download&confirm=9iBg&id=1N4y0HbgA3PHQ73ZxFJvy5dgvV_0cTBYF' \
    && unzip -o vocab.zip && mkdir -p /opt/ab3 && sha256sum vocab/mit_voc.yml > /opt/ab3/vocabulary_sha256.txt
COPY native/ab3_kimera_adapter $WORKSPACE/src/ab3_kimera_adapter
RUN source devel/setup.bash && catkin build -j"$BUILD_JOBS" ab3_kimera_adapter \
    && chmod +x $WORKSPACE/src/ab3_kimera_adapter/scripts/ab3_kimera_output.py \
    && echo "opengv_catkin $(git -C $WORKSPACE/src/opengv_catkin rev-parse HEAD) https://github.com/MIT-SPARK/opengv_catkin" \
       > /opt/ab3/dependency_commits.txt \
    && echo "mit_voc.yml $(cat /opt/ab3/vocabulary_sha256.txt)" >> /opt/ab3/dependency_commits.txt
COPY runtime /opt/ab3
ENV PYTHONUNBUFFERED=1 ROS_MASTER_URI=http://localhost:11311 ROS_HOSTNAME=localhost
ENTRYPOINT ["/bin/bash", "/opt/ab3/entrypoint_ros1.sh"]
