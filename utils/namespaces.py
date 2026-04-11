from data.cheats.gtav_cheats import Cheats_GTAV
from data.cheats.rdr2_cheats import Cheats_RDR2

from data.converter.rstar_converter import Converter_Rstar
from data.converter.bl3_converter import Converter_BL3
from data.converter.xeno2_converter import Converter_Xeno2

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
from data.crypto.sdew_crypt import Crypt_Sdew
from data.crypto.xeno2_crypt import Crypt_Xeno2
from data.crypto.nms_crypt import Crypt_NMS
from data.crypto.terraria_crypt import Crypt_Terraria
from data.crypto.smt5_crypt import Crypt_SMT5
from data.crypto.rcube_crypt import Crypt_RCube
from data.crypto.dsr_crypt import Crypt_DSR
from data.crypto.digimon_crypt import Crypt_Digimon
from data.crypto.nioh2_crypt import Crypt_Nioh2
from data.crypto.mhwi_crypt import Crypt_Mhwi
from data.crypto.lanoire_crypt import Crypt_LaNoire
from data.crypto.lohtrails_crypt import Crypt_LoHTrails
from data.crypto.minecraft_crypt import Crypt_Minecraft
from data.crypto.ff7cc_crypt import Crypt_FF7CC
from data.crypto.tosr_crypt import Crypt_ToSR
from data.crypto.re5_crypt import Crypt_RE5
from data.crypto.ccr_crypt import Crypt_CCR
from data.crypto.tob_crypt import Crypt_ToB
from data.crypto.tr6r_crypt import Crypt_TR6R
from data.crypto.strider_crypt import Crypt_Strider
from data.crypto.diablo3_crypt import Crypt_Diablo3
from data.crypto.alieniso_crypt import Crypt_AlienIso
from data.crypto.shantaescurse import Crypt_ShantaeSCurse
from data.crypto.mafia3_crypt import Crypt_Mafia3
from data.crypto.deadrising_crypt import Crypt_DeadRising
from data.crypto.kh3_crypt import Crypt_KH3
from data.crypto.popersia_crypt import Crypt_PoPersia
from data.crypto.lunarr_crypt import Crypt_LunarR

from types import SimpleNamespace

# NAMESPACES
Cheats = SimpleNamespace(GTAV=Cheats_GTAV, RDR2=Cheats_RDR2)
Converter = SimpleNamespace(Rstar=Converter_Rstar, BL3=Converter_BL3, Xeno2=Converter_Xeno2)
Crypto = SimpleNamespace(
    BL3=Crypt_BL3, Rstar=Crypt_Rstar, Xeno2=Crypt_Xeno2,
    Ndog=Crypt_Ndog, MGSV=Crypt_MGSV, Rev2=Crypt_Rev2,
    DL=Crypt_DL, RGG=Crypt_RGG, DI2=Crypt_DI2,
    NMS=Crypt_NMS, TERRARIA=Crypt_Terraria, SMT5=Crypt_SMT5,
    RCube=Crypt_RCube, RE7=Crypt_RE7, DSR=Crypt_DSR,
    RE4R=Crypt_RE4R, Digimon=Crypt_Digimon, Sdew=Crypt_Sdew,
    Nioh2=Crypt_Nioh2, Mhwi=Crypt_Mhwi, LaNoire=Crypt_LaNoire,
    LoHTrails=Crypt_LoHTrails, Minecraft=Crypt_Minecraft, FF7CC=Crypt_FF7CC,
    ToSR=Crypt_ToSR, RE5=Crypt_RE5, CCR=Crypt_CCR,
    ToB=Crypt_ToB, TR6R=Crypt_TR6R, Strider=Crypt_Strider,
    Diablo3=Crypt_Diablo3, AlienIso=Crypt_AlienIso, ShantaeSCurse=Crypt_ShantaeSCurse,
    Mafia3=Crypt_Mafia3, DeadRising=Crypt_DeadRising, KH3=Crypt_KH3,
    PoPersia=Crypt_PoPersia, LunarR=Crypt_LunarR
)

