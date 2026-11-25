# CBJ's Kitchen Engine

Drawing and rendering engine for **Cabinets by Johnny**. It turns a simple kitchen spec (JSON, inches) into:

- Floor plan with cabinet codes and dimension strings
- Elevations for every wall and island
- Cabinet and appliance order list (PDF page + CSV), with a "check before ordering" list
- Realistic 3D renders (Blender Cycles) using finish colors from the usadistributor.com catalog

Used by the `cbj-kitchen-designer` Claude skill.

```bash
bash setup.sh                       # prints RENDER_PY=...
python3 make_kitchen.py examples/sample_spec.json out --render normal --render-python <RENDER_PY>
```

Finish colors in `finishes.json` are approximations for on-screen presentation. Confirm every color with a door sample.
