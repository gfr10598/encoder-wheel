#!/usr/bin/env python3
import runpy, yaml, numpy as np, json, os, traceback
from scripts.analysis_utils import compute_field_from_magnets, analytic_rect_prism_B

def main():
    try:
        from scripts.common_config import load_config, validate_config
        cfg = load_config('examples/configs/n52_20x8x1.5_60_outer4in_sensor3p8in_fine.yaml')
        validate_config(cfg, ['outer_radius_mm', 'magnet_dims_mm'])
        outer = cfg['outer_radius_mm']
        mag_dims = cfg['magnet_dims_mm']
        Br = cfg.get('Br_T',1.45)
        mag_center = [outer - mag_dims[0]/2.0, 0.0, mag_dims[2]/2.0]
        mag = {'center':mag_center, 'dims':mag_dims, 'axis':(0,0,1), 'Br':Br}
        sensor_r = outer - 5.0
        airgap = 5.0
        # sensor z measured from magnet top face (magnet top = magnet thickness)
        sensor_pos = np.array([sensor_r/1000.0, 0.0, (mag_dims[2] + airgap)/1000.0])
        print('sensor_pos_m:', sensor_pos)
        gp = runpy.run_path('scripts/gemini-field-formula.py')
        if 'compute_magnetic_field_mm' not in gp:
            raise SystemExit('Gemini function not found')
        compute_magnetic_field_mm = gp['compute_magnetic_field_mm']
        pos_mm = (sensor_pos - np.array(mag_center)/1000.0) * 1000.0
        dims_half = [d/2.0 for d in mag_dims]
        B_gemini = compute_magnetic_field_mm(pos_mm.tolist(), dims_half, Br)
        print('B_gemini (T):', B_gemini)
        # original analytic
        B_analytic = analytic_rect_prism_B(mag_center, mag_dims, mag['axis'], sensor_pos, Br=Br)
        print('B_analytic (T):', B_analytic)
        # analytic adapted to gemini (delegates to gemini formula)
        B_analytic_gemini = analytic_rect_prism_B(mag_center, mag_dims, mag['axis'], sensor_pos, Br=Br, use_gemini=True)
        print('B_analytic_gemini (T):', B_analytic_gemini)
        Bnum = compute_field_from_magnets([mag], sensor_pos, model='discrete', Br=Br, discrete_grid=(16,16,8), steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
        print('B_numeric (T):', Bnum)
        out = {'analytic':B_analytic.tolist(), 'analytic_gemini': list(B_analytic_gemini), 'gemini':B_gemini.tolist(), 'numeric':Bnum.tolist(), 'sensor_pos_m': sensor_pos.tolist()}
        os.makedirs('examples/plots', exist_ok=True)
        with open('examples/plots/tmp_compare.json','w') as f:
            json.dump(out,f,indent=2)
        print('wrote examples/plots/tmp_compare.json')
        # create component comparison plot
        try:
            import matplotlib.pyplot as plt
            labels = ['Bx','By','Bz']
            analytic_vals = np.array(B_analytic)
            analytic_gem_vals = np.array(B_analytic_gemini)
            gemini_vals = np.array(B_gemini)
            numeric_vals = np.array(Bnum)
            x = np.arange(len(labels))
            width = 0.2
            plt.figure(figsize=(6,4))
            plt.bar(x - 1.5*width, analytic_vals, width, label='analytic')
            plt.bar(x - 0.5*width, analytic_gem_vals, width, label='analytic_gemini')
            plt.bar(x + 0.5*width, gemini_vals, width, label='gemini')
            plt.bar(x + 1.5*width, numeric_vals, width, label='numeric')
            plt.xticks(x, labels)
            plt.ylabel('B (T)')
            plt.title('Component comparison at sensor')
            plt.legend(); plt.tight_layout()
            plt.savefig('examples/plots/tmp_compare_components.png')
            print('wrote examples/plots/tmp_compare_components.png')
        except Exception as e:
            print('Failed to write comparison plot:', e)
    except Exception:
        traceback.print_exc()

if __name__ == '__main__':
    main()
