# Contributing

Keep changes focused on transparent management-planning calculations. Document any new assumption, units, payment timing, formula, boundary, and limitation. Add independently calculated examples or conservation tests for changes to the engine.

Run `python3 -m unittest discover -s tests -v` and `python3 scripts/verify_repository.py`. After changing the sample or output formatting, regenerate examples with `python3 -m smb_forecast forecast examples/sample-business.json --out examples/outputs`.

Use synthetic data only. Do not add client material, credentials, advice, external tracking, or unexplained calculation shortcuts. Runtime dependencies require a clear purpose and review. The existing engine/dashboard require none.
