# NEBULA successor PoC

The brief (requirements, established facts, architecture, steps, acceptance
criteria, open questions) lives in the vault, project `NEBULA_2.0`:
run `vault brief NEBULA_2.0`. Read it before working here.

- Toolchain comes from `flake.nix`: run builds as `nix develop --command make …`.
  `make` is not installed system-wide.
- Never edit `content/` to make a generator work; refresh it only with
  `make content`.
