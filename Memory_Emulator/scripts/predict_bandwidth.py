import numpy as np

def get_predicted_bandwidth(app_name, dram_percentage):
    """
    Predicts bandwidth based on DRAM percentage using:
    - Weighted 5th-degree polynomial for Bandwidth Bound.
    - Log-space 4th-degree polynomial for Latency Bound.
    To Determine which curve to fit, extract Stall chains from MemSim output.
    """
    # Convert percentage (0-100) to ratio (0.0-1.0)
    p = dram_percentage / 100.0
    
    # Constants derived from specific hardware formulas (Factor = N / D)
    factors = {
        'FT':  (599907 * 64 * 1e9) / ((1024**3) * 60097230),
        'SP':  (60555702 * 64 * 1e9) / ((1024**3) * 439646523),
        'BT':  (20893455 * 64 * 1e9) / ((1024**3) * 176193280),
        'BFS': (599907 * 64 * 1e9) / ((1024**3) * 60097230),
        'BC':  (6794781 * 64 * 1e9) / ((1024**3) * 76330642),
        'CC':  (747081 * 64 * 1e9) / ((1024**3) * 51489566),
    }

    # Coefficients for the apps with the "check-mark" behavior, Bandwidth Bound
    # Model: x = c5*p^5 + ... + c0
    coeffs_linear = {
        'FT': [0.8445644385597215, -1.8756355252074162, 1.4380628277426428, -0.4278528701716903, -0.0714656078160854, 0.10916247756468433],
        'SP': [10.816406562880623, -24.033741352931276, 18.72057742719681, -5.770991848052286, -1.3514393193549943, 1.9214579921290948],
        'BT': [6.61946902715919, -14.537285149548069, 11.602481030668494, -3.6998658070916535, -1.406010444672995, 1.8532446157698605],
    }
    
    # Coefficients for the apps with high dynamic range/decay,  Latency Bound
    # Model: log(x) = c4*p^4 + ... + c0
    coeffs_log = {
        'BFS': [12.037037272847739, -28.05783696770205, 23.75645634993109, -11.52227695767923, 2.520273872041989],
        'BC':  [26.148265546265144, -63.07746802756652, 53.184644055924664, -21.86757344857231, 4.281726017951843],
        'CC':  [19.725077384039544, -45.09790607080975, 36.54687047198825, -15.667633315486052, 3.0310983988246747],
    }

    if app_name in coeffs_linear:
        # Calculate x directly
        x = np.poly1d(coeffs_linear[app_name])(p)
    elif app_name in coeffs_log:
        # Calculate log(x), then exp() to ensure positive result
        log_x = np.poly1d(coeffs_log[app_name])(p)
        x = np.exp(log_x)
    else:
        return None

    # Protect against division by zero
    if x <= 0: return 0.0
    
    return factors[app_name] / x

def main():
    apps = ['FT', 'SP', 'BT', 'BFS', 'BC', 'CC']
    
    # Print Header
    header = f"{'DRAM %':<8} | " + " | ".join([f"{app:<8}" for app in apps])
    print(header)
    print("-" * len(header))

    # Iterate 100 down to 0 in steps of 10
    for i in range(100, -1, -10):
        row = f"{i:<8} | "
        for app in apps:
            bw = get_predicted_bandwidth(app, i)
            row += f"{bw:<8.4f} | "
        print(row)

if __name__ == "__main__":
    main()