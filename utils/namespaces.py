from data.cheats import Cheats_GTAV, Cheats_RDR2
from data.converter import Converter_Rstar, Converter_BL3
from data.crypto import (
    Crypt_Rstar, Crypt_Rev2, Crypt_BL3, Crypt_DI2, Crypt_DL, Crypt_MGSV, Crypt_Ndog, Crypt_RGG, Crypt_Xeno2, Crypt_NMS,
    Crypt_Terraria, Crypt_SMT5
)
from types import SimpleNamespace

# NAMESPACES
Cheats = SimpleNamespace(GTAV=Cheats_GTAV, RDR2=Cheats_RDR2)
Converter = SimpleNamespace(Rstar=Converter_Rstar, BL3=Converter_BL3)
Crypto = SimpleNamespace(
    BL3=Crypt_BL3, Rstar=Crypt_Rstar, Xeno2=Crypt_Xeno2, 
    Ndog=Crypt_Ndog, MGSV=Crypt_MGSV, Rev=Crypt_Rev2,
    DL=Crypt_DL, RGG=Crypt_RGG, DI2=Crypt_DI2, 
    NMS=Crypt_NMS, TERRARIA=Crypt_Terraria, SMT5=Crypt_SMT5
)