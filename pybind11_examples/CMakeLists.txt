cmake_minimum_required(VERSION 3.0.0)
project(pybind11_examples VERSION 0.1.0 LANGUAGE CXX)

# --------------------------------------------------------------------------- #
# OPTIONS
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# PYBIND11
# --------------------------------------------------------------------------- #
IF(IS_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/pybind11")
    message(STATUS "Adding pybind11 subdirectory.")
    add_subdirectory(pybind11)
ELSE()
    message(STATUS "Searching for pybind11...")
    find_package(pybind11 REQUIRED)
ENDIF()


pybind11_add_module(example example.cpp)


