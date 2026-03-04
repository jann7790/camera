/*
 * cctag_binding.cpp
 * pybind11 wrapper — exposes the official CCTag C++ detection API to Python.
 *
 * Exported Python module: _cctag_native
 *
 * Usage (Python):
 *   import _cctag_native as cn
 *
 *   # --- New: persistent Detector (recommended) ---
 *   det = cn.Detector(num_crowns=3)
 *   det.max_seeds = 100            # tune parameters before first detect()
 *   det.search_another_segment = False
 *   results = det.detect(gray_numpy_uint8)
 *
 *   # --- Legacy free-function (kept for backward compatibility) ---
 *   results = cn.detect(gray_numpy_uint8, num_crowns=3)
 */

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <cctag/Detection.hpp>
#include <cctag/CCTagMarkersBank.hpp>
#include <cctag/Params.hpp>
#include <cctag/CCTag.hpp>

#include <opencv2/core/core.hpp>

#include <stdexcept>
#include <memory>
#include <vector>
#include <map>
#include <string>

namespace py = pybind11;

// ── Helper: convert marker list to Python list of dicts ─────────────────────
static py::list markers_to_pylist(const cctag::CCTag::List& markers)
{
    py::list result;
    for (const auto& tag : markers) {
        const auto& ell = tag.rescaledOuterEllipse();
        py::dict d;
        d["id"]                = static_cast<int>(tag.id());
        d["status"]            = tag.getStatus();
        d["quality"]           = static_cast<double>(tag.quality());
        d["x"]                 = static_cast<double>(tag.x());
        d["y"]                 = static_cast<double>(tag.y());
        d["ellipse_cx"]        = static_cast<double>(ell.center().x());
        d["ellipse_cy"]        = static_cast<double>(ell.center().y());
        d["ellipse_a"]         = static_cast<double>(ell.a());
        d["ellipse_b"]         = static_cast<double>(ell.b());
        d["ellipse_angle_rad"] = static_cast<double>(ell.angle());
        result.append(d);
    }
    return result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Detector class — persistent Parameters + MarkersBank (created once, reused)
// ═══════════════════════════════════════════════════════════════════════════════

class Detector {
public:
    explicit Detector(std::size_t num_crowns = 3)
        : _params(num_crowns)
        , _bank(_params._nCrowns)
    {}

    // ── run detection ───────────────────────────────────────────────────────
    py::list detect(
        py::array_t<uint8_t, py::array::c_style | py::array::forcecast> gray_array,
        int         pipe_id  = 0,
        std::size_t frame_id = 0)
    {
        if (gray_array.ndim() != 2)
            throw std::invalid_argument("Input must be a 2-D (H x W) uint8 numpy array");

        auto buf = gray_array.request();
        int rows = static_cast<int>(buf.shape[0]);
        int cols = static_cast<int>(buf.shape[1]);

        cv::Mat img_gray(rows, cols, CV_8UC1, buf.ptr);

        // Sync _nCircles in case _nCrowns was changed
        _params._nCircles = 2 * _params._nCrowns;

        cctag::CCTag::List markers;
        cctag::cctagDetection(
            markers,
            pipe_id,
            frame_id,
            img_gray,
            _params,
            _bank,
            false,    // bDisplayEllipses
            nullptr   // durations
        );

        return markers_to_pylist(markers);
    }

    // ── access to Parameters fields ─────────────────────────────────────────
    cctag::Parameters _params;
    cctag::CCTagMarkersBank _bank;
};

// ═══════════════════════════════════════════════════════════════════════════════
// Legacy free-function (backward compatible)
// ═══════════════════════════════════════════════════════════════════════════════

py::list detect(
    py::array_t<uint8_t, py::array::c_style | py::array::forcecast> gray_array,
    std::size_t num_crowns = 3,
    int         pipe_id    = 0,
    std::size_t frame_id   = 0)
{
    if (gray_array.ndim() != 2)
        throw std::invalid_argument("Input must be a 2-D (H x W) uint8 numpy array");

    auto buf = gray_array.request();
    int rows = static_cast<int>(buf.shape[0]);
    int cols = static_cast<int>(buf.shape[1]);

    cv::Mat img_gray(rows, cols, CV_8UC1, buf.ptr);

    cctag::Parameters params(num_crowns);
    cctag::CCTagMarkersBank bank(params._nCrowns);

    cctag::CCTag::List markers;
    cctag::cctagDetection(
        markers,
        pipe_id,
        frame_id,
        img_gray,
        params,
        bank,
        false,
        nullptr
    );

    return markers_to_pylist(markers);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Module definition
// ═══════════════════════════════════════════════════════════════════════════════

PYBIND11_MODULE(_cctag_native, m)
{
    m.doc() = "Python bindings for the official CCTag C++ detection library";

    // ── Detector class ──────────────────────────────────────────────────────
    py::class_<Detector>(m, "Detector",
        R"doc(
Persistent CCTag detector.

Parameters and MarkersBank are created once at construction and reused
across calls to detect(), avoiding per-frame initialization overhead.

Parameters
----------
num_crowns : int, optional
    Number of rings: 3 for CCTag3 (default), 4 for CCTag4.
)doc")
        .def(py::init<std::size_t>(),
             py::arg("num_crowns") = 3)

        .def("detect", &Detector::detect,
             py::arg("gray_array"),
             py::arg("pipe_id")  = 0,
             py::arg("frame_id") = 0,
             R"doc(
Run CCTag detection on a grayscale image.

Parameters
----------
gray_array : numpy.ndarray, dtype=uint8, shape=(H, W)
    Grayscale input image.
pipe_id : int, optional
    CUDA pipeline index (ignored in CPU-only build). Default 0.
frame_id : int, optional
    Arbitrary frame counter for debug logging. Default 0.

Returns
-------
list of dict
    Each dict has: id, status, quality, x, y,
    ellipse_cx, ellipse_cy, ellipse_a, ellipse_b, ellipse_angle_rad
)doc")

        // ── Canny / Gradient ────────────────────────────────────────────────
        .def_property("canny_thr_low",
            [](const Detector& d) { return d._params._cannyThrLow; },
            [](Detector& d, float v) { d._params._cannyThrLow = v; },
            "Canny low threshold (default 0.01)")
        .def_property("canny_thr_high",
            [](const Detector& d) { return d._params._cannyThrHigh; },
            [](Detector& d, float v) { d._params._cannyThrHigh = v; },
            "Canny high threshold (default 0.04)")
        .def_property("thr_gradient_mag",
            [](const Detector& d) { return d._params._thrGradientMagInVote; },
            [](Detector& d, int v) { d._params._thrGradientMagInVote = v; },
            "Gradient magnitude threshold in voting (default 2500)")
        .def_property("max_edges",
            [](const Detector& d) { return d._params._maxEdges; },
            [](Detector& d, uint32_t v) { d._params._maxEdges = v; },
            "Maximum number of edge points (default 20000)")

        // ── Candidate search / Voting ───────────────────────────────────────
        .def_property("dist_search",
            [](const Detector& d) { return d._params._distSearch; },
            [](Detector& d, std::size_t v) { d._params._distSearch = v; },
            "Max search distance between edge points in pixels (default 30)")
        .def_property("angle_voting",
            [](const Detector& d) { return d._params._angleVoting; },
            [](Detector& d, float v) { d._params._angleVoting = v; },
            "Max angle between gradient directions of consecutive edge points (default 0.0)")
        .def_property("ratio_voting",
            [](const Detector& d) { return d._params._ratioVoting; },
            [](Detector& d, float v) { d._params._ratioVoting = v; },
            "Max distance ratio between consecutive edge points (default 4.0)")
        .def_property("average_vote_min",
            [](const Detector& d) { return d._params._averageVoteMin; },
            [](Detector& d, float v) { d._params._averageVoteMin = v; },
            "Minimum average vote (default 0.0)")
        .def_property("max_seeds",
            [](const Detector& d) { return d._params._maximumNbSeeds; },
            [](Detector& d, std::size_t v) { d._params._maximumNbSeeds = v; },
            "Maximum number of seed candidates to process (default 500)")
        .def_property("max_candidates_loop2",
            [](const Detector& d) { return d._params._maximumNbCandidatesLoopTwo; },
            [](Detector& d, std::size_t v) { d._params._maximumNbCandidatesLoopTwo = v; },
            "Maximum candidates in second loop (default 40)")
        .def_property("min_votes",
            [](const Detector& d) { return d._params._minVotesToSelectCandidate; },
            [](Detector& d, std::size_t v) { d._params._minVotesToSelectCandidate = v; },
            "Minimum votes to select an edge point as seed (default 3)")

        // ── Ellipse fitting ─────────────────────────────────────────────────
        .def_property("min_points_segment",
            [](const Detector& d) { return d._params._minPointsSegmentCandidate; },
            [](Detector& d, std::size_t v) { d._params._minPointsSegmentCandidate = v; },
            "Min points on outer ellipse to consider inner segment candidate (default 10)")
        .def_property("thr_median_dist_ellipse",
            [](const Detector& d) { return d._params._thrMedianDistanceEllipse; },
            [](Detector& d, float v) { d._params._thrMedianDistanceEllipse = v; },
            "Median distance threshold for ellipse fitting (default 3.0)")
        .def_property("thresh_robust_ellipse",
            [](const Detector& d) { return d._params._threshRobustEstimationOfOuterEllipse; },
            [](Detector& d, float v) { d._params._threshRobustEstimationOfOuterEllipse = v; },
            "LMeDs threshold for robust estimation of outer ellipse (default 30.0)")
        .def_property("ellipse_hull_width",
            [](const Detector& d) { return d._params._ellipseGrowingEllipticHullWidth; },
            [](Detector& d, float v) { d._params._ellipseGrowingEllipticHullWidth = v; },
            "Ellipse growing hull width in pixels (default 2.3)")
        .def_property("window_inner_segment",
            [](const Detector& d) { return d._params._windowSizeOnInnerEllipticSegment; },
            [](Detector& d, std::size_t v) { d._params._windowSizeOnInnerEllipticSegment = v; },
            "Window size on inner elliptic segment (default 20)")
        .def_property("search_another_segment",
            [](const Detector& d) { return d._params._searchForAnotherSegment; },
            [](Detector& d, bool v) { d._params._searchForAnotherSegment = v; },
            "Whether to search for another arc segment (default true). Set false to skip.")

        // ── Multi-resolution ────────────────────────────────────────────────
        .def_property("num_multires_layers",
            [](const Detector& d) { return d._params._numberOfMultiresLayers; },
            [](Detector& d, std::size_t v) { d._params._numberOfMultiresLayers = v; },
            "Number of multi-resolution layers (default 4)")
        .def_property("processed_multires_layers",
            [](const Detector& d) { return d._params._numberOfProcessedMultiresLayers; },
            [](Detector& d, std::size_t v) { d._params._numberOfProcessedMultiresLayers = v; },
            "Number of processed multi-resolution layers (default 4). Lower = faster.")

        // ── Identification ──────────────────────────────────────────────────
        .def_property("n_samples_outer",
            [](const Detector& d) { return d._params._nSamplesOuterEllipse; },
            [](Detector& d, std::size_t v) { d._params._nSamplesOuterEllipse = v; },
            "Number of samples on outer ellipse for identification (default 150)")
        .def_property("num_cuts_ident",
            [](const Detector& d) { return d._params._numCutsInIdentStep; },
            [](Detector& d, std::size_t v) { d._params._numCutsInIdentStep = v; },
            "Number of cuts in identification step (default 22)")
        .def_property("num_samples_refinement",
            [](const Detector& d) { return d._params._numSamplesOuterEdgePointsRefinement; },
            [](Detector& d, std::size_t v) { d._params._numSamplesOuterEdgePointsRefinement = v; },
            "Number of samples for outer edge points refinement (default 20)")
        .def_property("cuts_selection_trials",
            [](const Detector& d) { return d._params._cutsSelectionTrials; },
            [](Detector& d, std::size_t v) { d._params._cutsSelectionTrials = v; },
            "Number of trials in cuts selection (default 500). Lower for fewer tag IDs.")
        .def_property("sample_cut_length",
            [](const Detector& d) { return d._params._sampleCutLength; },
            [](Detector& d, std::size_t v) { d._params._sampleCutLength = v; },
            "Sample cut length (default 100)")
        .def_property("center_grid_sample",
            [](const Detector& d) { return d._params._imagedCenterNGridSample; },
            [](Detector& d, std::size_t v) { d._params._imagedCenterNGridSample = v; },
            "Center grid sample count per side, must be odd (default 5 -> 25 points)")
        .def_property("center_neighbour_size",
            [](const Detector& d) { return d._params._imagedCenterNeighbourSize; },
            [](Detector& d, float v) { d._params._imagedCenterNeighbourSize = v; },
            "Center neighbourhood size relative to outer ellipse semi-axis (default 0.20)")
        .def_property("min_ident_proba",
            [](const Detector& d) { return d._params._minIdentProba; },
            [](Detector& d, float v) { d._params._minIdentProba = v; },
            "Minimum identification probability threshold (default 1e-6)")
        .def_property("use_lmdif",
            [](const Detector& d) { return d._params._useLMDif; },
            [](Detector& d, bool v) { d._params._useLMDif = v; },
            "Use Levenberg-Marquardt refinement (default true). Set false to speed up.")
        .def_property("do_identification",
            [](const Detector& d) { return d._params._doIdentification; },
            [](Detector& d, bool v) { d._params._doIdentification = v; },
            "Perform identification step (default true). Set false for localization only.")
    ;

    // ── Legacy free-function ────────────────────────────────────────────────
    m.def(
        "detect",
        &detect,
        py::arg("gray_array"),
        py::arg("num_crowns") = 3,
        py::arg("pipe_id")    = 0,
        py::arg("frame_id")   = 0,
        R"doc(
Run official CCTag detection on a grayscale image (legacy API).

NOTE: This creates Parameters and MarkersBank on every call.
      For better performance, use the Detector class instead.

Parameters
----------
gray_array : numpy.ndarray, dtype=uint8, shape=(H, W)
    Grayscale input image.
num_crowns : int, optional
    Number of rings: 3 for CCTag3 (default), 4 for CCTag4.
pipe_id : int, optional
    CUDA pipeline index (ignored in CPU-only build). Default 0.
frame_id : int, optional
    Arbitrary frame counter used for debug logging. Default 0.

Returns
-------
list of dict
    Each dict has:
      id               (int)   – marker ID (-1 if unidentified)
      status           (int)   – 1 = valid detection
      quality          (float) – identification quality score
      x, y             (float) – marker centre in image pixels
      ellipse_cx/cy    (float) – outer ellipse centre
      ellipse_a/b      (float) – semi-axes of outer ellipse (pixels)
      ellipse_angle_rad(float) – ellipse orientation (radians, clock-wise)
)doc"
    );
}
