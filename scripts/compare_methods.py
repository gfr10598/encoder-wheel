#!/usr/bin/env python3
"""Compare dipole-superposition vs volumetric discretization for the full ring.
Produces overlay plots for airgaps 3 and 4 mm.
"""
import os, sys, math, yaml, argparse
import numpy as np
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
from analysis_utils import compute_field_from_magnets, analytic_rect_prism_B
from coords import cyl_to_cart


def build_ring_config(n_magnets, r_inner, magnet_dims, Br=1.45):
    r_center = r_inner + magnet_dims[0]/2.0
    mags = []
    for i in range(n_magnets):
        theta = 2*math.pi*i/n_magnets
        x = r_center*math.cos(theta)
        y = r_center*math.sin(theta)
        # poles through faces: axis perpendicular to disk (z); alternate polarity
        polarity = -1.0 if (i % 2) else 1.0
        axis_vec = (0.0, 0.0, polarity)
        # place magnet with its large face against disk (top of disk at z=0)
        mz = magnet_dims[2] / 2.0
        mags.append({'center': [x,y,0.0], 'dims': magnet_dims, 'axis': axis_vec, 'Br': Br})
    return mags


def compare(cfg, airgaps_mm, outdir, discrete_grid=(8,8,4)):
    n = cfg['n_magnets']
    outer = cfg['outer_radius_mm']
    sensor_offset_from_outer = float(cfg.get('sensor_offset_from_outer_mm', 5.0))
    sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
    magnet_dims = cfg['magnet_dims_mm']
    Br = cfg.get('Br_T', 1.45)
    theta_steps = cfg.get('theta_steps', 2048)
    r_inner = outer - magnet_dims[0]
    mags = build_ring_config(n, r_inner, magnet_dims, Br=Br)
    # adjust magnet center z so each magnet's large face sits at z=0 (disk top)
    mz = magnet_dims[2] / 2.0
    for m in mags:
        m['center'][2] = mz
    thetas = np.linspace(0,2*math.pi,theta_steps,endpoint=False)
    pole_pairs_window = cfg.get('pole_pairs_window', None)
    if pole_pairs_window is not None:
        try:
            pole_pairs_window = int(pole_pairs_window)
        except Exception:
            pole_pairs_window = None

    for ag in airgaps_mm:
        # sensor z is measured from magnet top face: magnet top = magnet_thickness (magnet lower face at z=0)
        sensor_z = (magnet_dims[2] + ag)/1000.0
        sensor_theta_deg = float(cfg.get('sensor_theta_deg', 0.0))
        sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
        bx_dip = np.zeros_like(thetas)
        by_dip = np.zeros_like(thetas)
        bx_num = np.zeros_like(thetas)
        by_num = np.zeros_like(thetas)
        for idx, th in enumerate(thetas):
            # optionally select a local window of magnets (pole pairs) for speed
            rotated = []
            if pole_pairs_window is None:
                sel_indices = range(n)
            else:
                total_mags = int(pole_pairs_window) * 2
                half_span = total_mags // 2
                pitch = 2*math.pi / n
                center_idx = int(round((-th) / pitch)) % n
                start = center_idx - half_span
                end = center_idx + half_span - 1
                sel_indices = [(i % n) for i in range(start, end+1)]
            for mi in sel_indices:
                m = mags[mi]
                c = np.array(m['center'])
                cr = np.array([c[0]*math.cos(th)-c[1]*math.sin(th), c[0]*math.sin(th)+c[1]*math.cos(th), c[2]])
                a = np.array(m['axis'])
                ar = np.array([a[0]*math.cos(th)-a[1]*math.sin(th), a[0]*math.sin(th)+a[1]*math.cos(th), a[2]])
                mm = dict(m)
                mm['center']=cr; mm['axis']=(float(ar[0]), float(ar[1]), float(ar[2])); rotated.append(mm)
            # sensor position in Cartesian computed from cylindrical coords
            sensor_pos = cyl_to_cart(sensor_r/1000.0, math.radians(sensor_theta_deg), sensor_z)
            Bdip = compute_field_from_magnets(rotated, sensor_pos, model='dipole', Br=Br, discrete_grid=(1,1,1), steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
            Bnum = compute_field_from_magnets(rotated, sensor_pos, model='discrete', Br=Br, discrete_grid=discrete_grid, steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
            bx_dip[idx] = Bdip[0]; by_dip[idx] = Bdip[1]
            bx_num[idx] = Bnum[0]; by_num[idx] = Bnum[1]
            # analytic rectangular-prism sum (windowed)
            image_factor = None
            if cfg.get('steel_image_factor') is not None:
                image_factor = float(cfg.get('steel_image_factor'))
            elif cfg.get('steel_mu_r') is not None:
                mu_r = float(cfg.get('steel_mu_r'))
                image_factor = (mu_r - 1.0) / (mu_r + 1.0)
            plane_z = None
            if cfg.get('steel_plane_z') is not None:
                plane_z = float(cfg.get('steel_plane_z'))
            elif cfg.get('steel_backing_thickness_mm') is not None:
                # steel upper face at z=0
                plane_z = 0.0
            B_analytic_sum = np.zeros(3)
            for mm in rotated:
                Barr = analytic_rect_prism_B(mm['center'], mm['dims'], mm['axis'], sensor_pos, Br=mm.get('Br', Br))
                B_analytic_sum += Barr
                if image_factor is not None and plane_z is not None:
                    cm = np.array(mm['center'])/1000.0
                    cm_img = cm.copy(); cm_img[2] = 2*plane_z - cm[2]
                    # analytic expects center in mm
                    center_img_mm = (cm_img * 1000.0).tolist()
                    Barr_img = analytic_rect_prism_B(center_img_mm, mm['dims'], mm['axis'], sensor_pos, Br=mm.get('Br', Br))
                    B_analytic_sum += image_factor * Barr_img
            if 'bx_analytic' not in locals():
                bx_analytic = np.zeros_like(thetas)
                by_analytic = np.zeros_like(thetas)
            bx_analytic[idx] = B_analytic_sum[0]
            by_analytic[idx] = B_analytic_sum[1]
        # convert to mT and plot overlays (limited to window_deg for clarity)
        window_deg = cfg.get('window_deg', 36)
        degs = np.degrees(thetas)
        mask = (degs >= 0) & (degs <= window_deg)
        plt.figure(figsize=(9,4))
        plt.plot(degs[mask], bx_dip[mask]*1e3, label='Bx dipole', alpha=0.7)
        plt.plot(degs[mask], bx_num[mask]*1e3, '--', label=f'Bx numeric {discrete_grid}', alpha=0.7)
        plt.plot(degs[mask], bx_analytic[mask]*1e3, ':', label='Bx analytic', alpha=0.9)
        plt.xlabel('theta (deg)'); plt.ylabel('Bx (mT)'); plt.title(f'Bx: dipole vs numeric — airgap {ag} mm')
        plt.legend(); plt.tight_layout();
        plt.savefig(os.path.join(outdir,f'compare_bx_{int(ag)}mm.png'))
        plt.close()

        plt.figure(figsize=(9,4))
        plt.plot(degs[mask], by_dip[mask]*1e3, label='By dipole', alpha=0.7)
        plt.plot(degs[mask], by_num[mask]*1e3, '--', label=f'By numeric {discrete_grid}', alpha=0.7)
        plt.plot(degs[mask], by_analytic[mask]*1e3, ':', label='By analytic', alpha=0.9)
        plt.xlabel('theta (deg)'); plt.ylabel('By (mT)'); plt.title(f'By: dipole vs numeric — airgap {ag} mm')
        plt.legend(); plt.tight_layout();
        plt.savefig(os.path.join(outdir,f'compare_by_{int(ag)}mm.png'))
        plt.close()

        print(f'Wrote compare_bx_{int(ag)}mm.png and compare_by_{int(ag)}mm.png')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    p.add_argument('--airgaps', nargs='+', type=float, default=[3.0,4.0])
    p.add_argument('--outdir', default='examples/plots')
    p.add_argument('--grid', nargs=3, type=int, default=[8,8,4])
    args = p.parse_args()
    cfg = yaml.safe_load(open(args.config))
    os.makedirs(args.outdir, exist_ok=True)
    compare(cfg, args.airgaps, args.outdir, tuple(args.grid))
