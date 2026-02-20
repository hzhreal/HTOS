from utils.constants import MINECRAFT_TITLEID

class Crypt_Minecraft:
    @staticmethod
    def reregion_get_new_name(title_id: str, savepairname: str) -> str:
        savepairname = savepairname.split("-")
        # legacy edition only
        if not savepairname[0] in MINECRAFT_TITLEID:
            return ""
        savepairname[0] = title_id
        savepairname = "-".join(savepairname)
        return savepairname
