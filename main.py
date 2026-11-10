import multiprocessing
import os
import sys

# Programa sem janela preta: nesse modo o Windows nao fornece saida de texto,
# e algumas bibliotecas quebram se tentarem escrever nela.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("GLOG_minloglevel", "3")

from cortes.ui import iniciar

if __name__ == "__main__":
    multiprocessing.freeze_support()
    iniciar()
