cmake_minimum_required(VERSION 3.15)
project(cctag_python_binding CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Paths (conda base environment) ──────────────────────────────────────────
set(CONDA_PREFIX "$ENV{HOME}/miniconda3" CACHE PATH "Conda prefix")

set(CMAKE_PREFIX_PATH "${CONDA_PREFIX}" ${CMAKE_PREFIX_PATH})

# ── Find dependencies ────────────────────────────────────────────────────────
find_package(pybind11 REQUIRED)
find_package(CCTag    REQUIRED PATHS "${CONDA_PREFIX}/lib/cmake/CCTag")
find_package(OpenCV   REQUIRED COMPONENTS core imgproc)
find_package(Boost    REQUIRED COMPONENTS serialization)
find_package(TBB      REQUIRED PATHS "${CONDA_PREFIX}/lib/cmake/TBB")

# ── Build the extension module ───────────────────────────────────────────────
pybind11_add_module(_cctag_native
    ${CMAKE_CURRENT_SOURCE_DIR}/cctag_binding.cpp
)

target_include_directories(_cctag_native PRIVATE
    "${CONDA_PREFIX}/include"
)

target_link_libraries(_cctag_native PRIVATE
    CCTag::CCTag
    ${OpenCV_LIBS}
    Boost::serialization
    TBB::tbb
)

# Output to the lib/ directory in the project root
set_target_properties(_cctag_native PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../lib"
)
