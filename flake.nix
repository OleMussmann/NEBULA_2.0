{
  description = "NEBULA successor PoC: Quarto, Hugo and Astro Starlight variants";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in {
      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            gnumake
            git
            python3      # tools/build_study.py (stdlib only)
            quarto       # variant 1
            hugo         # variant 2 (extended edition)
            nodejs_22    # variant 3 (Astro Starlight) + Pagefind via npx
          ];
        };

        # Headless-browser checks: tools/verify_site.py (`make verify-<variant>`)
        verify = pkgs.mkShell {
          packages = with pkgs; [
            gnumake
            (python3.withPackages (ps: [ ps.playwright ]))
          ];
          PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
          PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = "true";
        };
      });
    };
}
