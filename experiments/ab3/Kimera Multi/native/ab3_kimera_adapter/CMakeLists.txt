# AB3 output node and launch file for the original Kimera-Multi (separate package; upstream untouched).
cmake_minimum_required(VERSION 3.0.2)
project(ab3_kimera_adapter)
find_package(catkin REQUIRED COMPONENTS rospy)
catkin_package()
catkin_install_python(PROGRAMS scripts/ab3_kimera_output.py DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})
install(DIRECTORY launch DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})
