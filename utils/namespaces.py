from data.cheats.gtav_cheats import Cheats_GTAV
from data.cheats.rdr2_cheats import Cheats_RDR2

from data.converter.rstar_converter import Converter_Rstar
from data.converter.bl3_converter import Converter_BL3

from data.crypto.rstar_crypt import Crypt_Rstar
from data.crypto.rev2_crypt import Crypt_Rev2
from data.crypto.re4r_crypt import Crypt_RE4R
from data.crypto.re7_crypt import Crypt_RE7
from data.crypto.bl3_crypt import Crypt_BL3
from data.crypto.di2_crypt import Crypt_DI2
from data.crypto.dl_crypt import Crypt_DL
from data.crypto.mgsv_crypt import Crypt_MGSV
from data.crypto.ndog_crypt import Crypt_Ndog
from data.crypto.rgg_crypt import Crypt_RGG
from data.crypto.xeno2_crypt import Crypt_Xeno2
from data.crypto.nms_crypt import Crypt_NMS
from data.crypto.terraria_crypt import Crypt_Terraria
from data.crypto.smt5_crypt import Crypt_SMT5
from data.crypto.rcube_crypt import Crypt_RCube
from data.crypto.dsr_crypt import Crypt_DSR

from types import SimpleNamespace

# NAMESPACES
Cheats = SimpleNamespace(GTAV=Cheats_GTAV, RDR2=Cheats_RDR2)
Converter = SimpleNamespace(Rstar=Converter_Rstar, BL3=Converter_BL3)
Crypto = SimpleNamespace(
    BL3=Crypt_BL3, Rstar=Crypt_Rstar, Xeno2=Crypt_Xeno2, 
    Ndog=Crypt_Ndog, MGSV=Crypt_MGSV, Rev2=Crypt_Rev2,
    DL=Crypt_DL, RGG=Crypt_RGG, DI2=Crypt_DI2, 
    NMS=Crypt_NMS, TERRARIA=Crypt_Terraria, SMT5=Crypt_SMT5,
    RCube=Crypt_RCube, RE7=Crypt_RE7, DSR=Crypt_DSR,
    RE4R=Crypt_RE4R
)