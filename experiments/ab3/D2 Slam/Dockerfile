# Official D2SLAM (HKUST-Aerial-Robotics) on CPU for the AB3 benchmark.
# Follows upstream docker/Dockerfile.x86_no_cuda, with every moving reference
# pinned in source_lock.json. No lidar, depth camera, GPS, RViz or GPU.
FROM --platform=linux/amd64 ros:noetic-perception-focal
SHELL ["/bin/bash", "-c"]
ARG BUILD_JOBS=2
ENV DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC
RUN apt-get update && apt-get install -y --no-install-recommends \
      tzdata wget curl git ca-certificates unzip build-essential \
      libatlas-base-dev libeigen3-dev libgoogle-glog-dev libgflags-dev libsuitesparse-dev \
      libglib2.0-dev libyaml-cpp-dev libdw-dev libboost-all-dev \
      python3-dev python3-pip python3-numpy python3-opencv python3-psutil python3-catkin-tools \
      ros-noetic-ros-base ros-noetic-nav-msgs ros-noetic-sensor-msgs ros-noetic-geometry-msgs \
      ros-noetic-visualization-msgs ros-noetic-cv-bridge ros-noetic-image-transport \
      ros-noetic-image-transport-plugins ros-noetic-message-filters ros-noetic-tf ros-noetic-pcl-ros \
    && rm -rf /var/lib/apt/lists/*
COPY source_lock.json /opt/benchmark/source_lock.json
COPY native/fetch_pinned.py /opt/benchmark/native/fetch_pinned.py
# Same CMake as upstream (focal's 3.16 is too old for the dependencies).
RUN wget -q https://github.com/Kitware/CMake/releases/download/v3.24.1/cmake-3.24.1-Linux-x86_64.sh -O /tmp/cmake.sh \
    && rm -f /usr/bin/cmake && sh /tmp/cmake.sh --skip-license --prefix=/usr && rm /tmp/cmake.sh && cmake --version
RUN python3 /opt/benchmark/native/fetch_pinned.py ceres_solver /tmp/ceres && cd /tmp/ceres && mkdir build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF -DBUILD_BENCHMARKS=OFF .. \
    && make -j"$BUILD_JOBS" install && rm -rf /tmp/ceres
# ONNX Runtime CPU package (upstream's no-CUDA file names the aarch64 package).
RUN wget -q https://github.com/microsoft/onnxruntime/releases/download/v1.18.0/onnxruntime-linux-x64-1.18.0.tgz -O /tmp/ort.tgz \
    && tar -xzf /tmp/ort.tgz -C /tmp && cp -r /tmp/onnxruntime-linux-x64-1.18.0/include/* /usr/local/include/ \
    && cp -r /tmp/onnxruntime-linux-x64-1.18.0/lib/* /usr/local/lib/ && rm -rf /tmp/ort.tgz /tmp/onnxruntime-linux-x64-1.18.0
RUN python3 /opt/benchmark/native/fetch_pinned.py lcm /tmp/lcm && cd /tmp/lcm && mkdir build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release -DLCM_ENABLE_PYTHON=OFF -DLCM_ENABLE_JAVA=OFF -DLCM_ENABLE_LUA=OFF \
             -DLCM_ENABLE_TESTS=OFF -DLCM_ENABLE_EXAMPLES=OFF .. \
    && make -j"$BUILD_JOBS" install \
    && python3 -m pip install --no-cache-dir 'lcm==1.4.0' \
    && cd / && rm -rf /tmp/lcm
# Generic x86-64 FAISS (runs on any amd64 host, including Apple Silicon emulation).
RUN python3 /opt/benchmark/native/fetch_pinned.py faiss /tmp/faiss && cd /tmp/faiss \
    && cmake -B build -DCMAKE_BUILD_TYPE=Release -DFAISS_OPT_LEVEL=generic -DFAISS_ENABLE_PYTHON=OFF \
             -DBUILD_TESTING=OFF -DFAISS_ENABLE_GPU=OFF . \
    && make -C build -j"$BUILD_JOBS" faiss && make -C build install && rm -rf /tmp/faiss
RUN python3 /opt/benchmark/native/fetch_pinned.py opengv /tmp/opengv && mkdir /tmp/opengv/build && cd /tmp/opengv/build \
    && cmake -DCMAKE_BUILD_TYPE=Release .. && make -j"$BUILD_JOBS" install && rm -rf /tmp/opengv
RUN python3 /opt/benchmark/native/fetch_pinned.py backward_cpp /tmp/backward \
    && cp /tmp/backward/backward.hpp /usr/local/include/backward.hpp && rm -rf /tmp/backward
RUN python3 /opt/benchmark/native/fetch_pinned.py spdlog /tmp/spdlog && mkdir /tmp/spdlog/build && cd /tmp/spdlog/build \
    && cmake -DCMAKE_BUILD_TYPE=Release .. && make -j"$BUILD_JOBS" install && rm -rf /tmp/spdlog
RUN wget -q 'https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-2.0.1%2Bcpu.zip' -O /tmp/libtorch.zip \
    && unzip -q /tmp/libtorch.zip -d /tmp && cp -r /tmp/libtorch/* /usr/local/ && rm -rf /tmp/libtorch.zip /tmp/libtorch \
    && ldconfig
# Unchanged pinned D2SLAM sources and the authors' models, checksum-verified.
COPY algorithm/D2SLAM-original.zip /opt/benchmark/D2SLAM-original.zip
COPY third_party/models /opt/d2models
COPY native/extract_original.py /opt/benchmark/native/extract_original.py
RUN python3 /opt/benchmark/native/extract_original.py
COPY tools/patch_runtime.py /opt/benchmark/tools/patch_runtime.py
COPY native/build_d2slam.sh /opt/benchmark/native/build_d2slam.sh
RUN bash /opt/benchmark/native/build_d2slam.sh "$BUILD_JOBS"
COPY config /opt/benchmark/config
COPY bridge /opt/benchmark/bridge
COPY native /opt/benchmark/native
RUN chmod +x /opt/benchmark/native/entrypoint.sh
ENTRYPOINT ["/opt/benchmark/native/entrypoint.sh"]
