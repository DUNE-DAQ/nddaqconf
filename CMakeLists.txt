cmake_minimum_required(VERSION 3.12)
project(daqconf VERSION 6.0.2)

find_package(daq-cmake REQUIRED )

daq_setup_environment()

daq_install()
