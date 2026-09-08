# Third-Party Notices

This repository redistributes vendor and community files that are **not** covered
by the root [LICENSE](LICENSE). They are listed below with the terms that do
apply. Under CERN-OHL-S §1.7 and §3.3(d) these are *Available Components* and
remain licensed under their own terms.

Nothing here restricts **manufacturing the board**. The gerbers, drill file and
`.kicad_pcb` are original work; the files below are 3D visualisation meshes and
reference documents that never enter the manufacturing output.

---

## 3D models

### LD2410C radar mesh — **CC BY-NC 4.0, non-commercial**
- Files: `hardware/3d/LD2410C mmWave Sensor.step`,
  `hardware/3d/ld2410c-mmwave-sensor-1.snapshot.2/` and the `.zip` beside it
- License: **Creative Commons Attribution-NonCommercial 4.0 International**
- License file: `hardware/3d/ld2410c-mmwave-sensor-1.snapshot.2/Creative Commons Non-Commercial License.jpg`
- Source: **GrabCAD** — https://grabcad.com/library/ld2410c-mmwave-sensor-1
- Modifications: none
- **This is the only non-commercially-licensed file in the repository.** It is
  the mesh shown for U2 in the 3D viewer. If you are doing anything commercial,
  delete these three paths and use the Hi-Link model below instead — the board,
  the gerbers and every other file remain usable, because this mesh contributes
  nothing to the fabrication outputs.
- ⚠️ **The uploader's name is not yet recorded here.** CC BY-NC requires credit
  to the author. The model's own metadata does not carry it — the STEP header
  has empty `author` and `organization` fields and the archive has no comment —
  and GrabCAD requires a login to view the uploader, so it could not be read
  from the file or the public page. **Please obtain the model from the GrabCAD
  link above rather than relying on this copy for attribution**, until the
  uploader's name is added to this notice.

### HLK-LD2410C manufacturer mesh
- Files: `hardware/3d/HLK-LD2410C-3D图/`, `hardware/3d/HLK-LD2410C-3D图.zip`,
  and the duplicate copy at `docs/LD2410C Docs/HLK-LD2410C-3D图.zip`
- Source: Hi-Link Electronics, distributed with the LD2410C documentation package
- License: no explicit grant; redistributed as a manufacturer-supplied support file
- Modifications: none

### Seeed XIAO ESP32-C3 mesh
- File: `hardware/3d/Seeed-Studio-XIAO-ESP32-C3.step`
- Source: Seeed Studio, vendor-supplied CAD for the XIAO ESP32-C3
- Modifications: none

### Adafruit VEML7700 symbol and footprint — **redistribution restricted**
- File: `hardware/3d/Adafruit VEML7700.zip`
- Source: **SnapMagic** (formerly SamacSys), part model for the Adafruit 4162
- License: `License.txt` inside the archive. The models remain SnapMagic's
  intellectual property. Clause 1(a) restricts distributing the models to third
  parties. **The permission to use this repository's own license does not extend
  to this archive** — obtain the models from SnapMagic directly.
- Modifications: none
- Note: nothing in the board references this part. The VEML7700 sits off-board on
  a QT cable, so the archive is a convenience copy only and can be deleted with
  no effect on the design.

### Mechanical hardware meshes
- `hardware/3d/M3 Screw.stp` — vendor CAD download; the STEP header records the
  original part reference `97790603111`. Origin not recorded in this repository.
- `hardware/3d/hexagonal_spacer_FF_M3_H10_HEX5.5_pass_through.step` — community
  FreeCAD model. Origin not recorded in this repository.
- `hardware/3d/Dupont Jumper Wire F-F.step` — community model. Origin not
  recorded in this repository.

  These three are generic fastener and jumper meshes used for assembly
  visualisation only. Their provenance was not captured when they were
  downloaded; if you need to rely on them, source your own copies.

## Documentation

### Hi-Link LD2410C datasheet and serial protocol
- `docs/LD2410C Docs/HLK LD2410C Life Presence Sensor Module Data Sheet V1.00.pdf`
- `docs/LD2410C Docs/HLK-LD2410C Serial communication protocol V1.07.pdf`
- `docs/LD2410C Docs/HLK-LD2410 Tool EN-20260905T181157Z-1-001.zip`
- Source: Hi-Link Electronics. Copyright Hi-Link; redistributed as the primary
  reference the design document cites throughout.

### Adafruit VEML7700 guide
- `docs/LD2410C Docs/adafruit-veml7700.pdf`
- Source: Adafruit Industries. Adafruit learning-system guides are published
  under CC BY-SA 3.0 unless stated otherwise in the document.

## Referenced but not redistributed

The board also references 3D models from the KiCad standard libraries
(`${KICAD10_3DMODEL_DIR}`) and from the Fab library installed through the KiCad
Plugin and Content Manager (`${KICAD9_3RD_PARTY}`). Those files are **not**
included here and are resolved from your local KiCad installation.
