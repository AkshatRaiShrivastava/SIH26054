# ML Model

## Approach

One Isolation Forest model is trained for each operating environment. A deterministic rule layer translates anomaly evidence into an explainable possible contributing category.

## Live Window

The backend buffers 15 ordered packets for a mission/environment and scores every five packets after warm-up. It converts simulator units to the model contract:

| Simulator | ML input |
| --- | --- |
| Oil pressure psi | Oil pressure kPa |
| Vibration g | Vibration mm/s |
| Oil temperature C | Oil temperature C |
| Electrical values | Battery, bus, alternator inputs |

## Output

The output includes anomaly evidence, calibrated threshold, ML/rule flags, category, confidence, driving features, and rule evidence. Rule evidence gives matched direction and baseline deviation for each relevant parameter.

## Limitation

The supplied training data is healthy-only. Synthetic faults support regression testing but do not demonstrate operational fault accuracy. Do not use output for safety-critical control. Remaining useful life prediction is not implemented.
