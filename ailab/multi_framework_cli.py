from __future__ import annotations
import argparse,json
from .multi_framework import *
def main(argv=None):
 argparse.ArgumentParser().parse_args(argv);models=[train_linear([1,2,3],[3,5,7],name) for name in ("pytorch","tensorflow","jax")];print(json.dumps({"inventory":installed_frameworks(),"parity":parity(models,[1,2,3]),"prediction":models[0].predict(4)},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
