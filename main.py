import requests
from requests.models import get_auth_from_url
from url import LOGIN_URL, SERIES_DATA, EPISODE_DATA, MOVIE_DETAIL, USER_DATA
import pathlib
import sys
import os
import argparse
from Crypto.Cipher import AES
from config import USERNAME, PASSWORD
import concurrent.futures

os.chdir(pathlib.Path(__file__).parent.resolve())

class LoginError(Exception):
    def __init__(self, message):
        super().__init__(message)

class FindEpisodeError(Exception):
    def __init__(self, message):
        super().__init__(message)
    
class SubscriptionError(Exception):
    def __init__(self, message):
        super().__init__(message)

class FileNotSupported(Exception):
    def __init__(self, message):
        super().__init__(message)

class Namava:
    def __init__(self, movie_url: str, season: int = 1, episode: int = 1) -> None:
        self.token = ""
        self.movie_url = movie_url
        self.season = season
        self.episode = episode

    def login(self, username: str, password: str) -> str:
        """
        return token
        """
        print("Logging in...")
        request = requests.post(LOGIN_URL, data={"UserName": username, "Password": password}, headers=self.create_header()).json()

        if request["succeeded"]:
            print("Login successful!")
            self.token = request["result"]
        
        else:
            raise LoginError("username or password is wrong")

    def has_subscription(self) -> bool:
        print("Checking subscription...")
        user_data = requests.get(USER_DATA, headers=self.create_header()).json()["result"]["subscription"]
        #if user_data["validFromDate"]
        if user_data["validFromDate"] != None and user_data["validToDate"] != None:
            print("Subscription found")
            return True
        return False

    def create_header(self) -> dict:
        return {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
            "cookie": 'guest_token=' + self.token + '; rb_guest_token=9FA261B03832154D68EBDA506D8B47EF2C48F36D2ADF074BF438D0FB590E94AD2486B6745A50669C3A77BE0CE662AED06C7E0C28A55FE511E73F47384AEB07D6CEAFDE42191D6D0730A7BB8D9B357581D26FD218AB25628AEA1596736CE1829B754E18BC0D04DBA1188FA568492A584C75B83DBC875C26F48237D807F7CB6F921B6D3F5DA914FBE4ED9D6E66864920693FDA3EE11C3A1CAA58BE1126C52BFE0FA75FA174752579D95A90060A4115855115E7C0242A33F324D07F21742933DAD18D12DCA055FAEA1AC4170AE41BA36A75B01DB8DA8CECD484F6071E191A420A9BE41E4155764BE0436E260D5E7027B080; rb_anonymous_login=true; notification=true; _ga_X8RD5LS5K2=GS1.1.1640700353.1.1.1640700379.0; use_legacy_player=false; dv-v3={"g":"desktop","platform":null}; _clck=1f4u8if|1|ey5|0; _gid=GA1.2.570019664.1642267550; content_viewed=128302; _gat_UA-107442781-1=1; last_user_update=1642267828284; profile_update=1642267828284; anonymous_login=true; auth_return=eyJwYXRobmFtZSI6Ii8ifQ; _ga=GA1.2.884584504.1639002317; _clsk=1yms85f|1642267837442|15|0|www.clarity.ms/eus2/collect; auth_v2=95F1C1B7ADB38DEA0F9012F474D8633D05923E11AC3A0442AF931318C0F578AA928B6DB838B8CD0FF2C34C1D9501FE1A3F6028E210FBEE1660BF8CA5E0B1FCB00D7A73547EA067CDC9DBCEEF967AEE240B49CC9E2A97603B5C551DACAA77107D1A04B887DB202F188B16D413B12D330F4912FCED3B075A38B4C886EE9BB69BDF9AE92E1CAD45253EB73615ABEF323906899EB5ED9815D4E318ACD9598CBC5EABB8AA27BAD43FC5EF9C215920689ED24D5AAA183170610CDDACEFF505F22EB56ADFAE73AE79BA31E044F7EC2AE9365E8F4BDC567F5E3BBF4E7CAA8560B2A57C133674EB974DA4B6C9A8922F5D65D1E201; auth_token=; _ga_TLHYT3BK0M=GS1.1.1642267523.57.1.1642267841.0; webengage=true'
        }

    def get_movie_id(self) -> str:
        return self.movie_url.split("/")[-1].split("-")[0]

    def get_season_id(self) -> int:
        """
        movie_url example: https://www.namava.ir/series/115791-%D8%A8%D8%A7%D8%B2%DB%8C_%D9%85%D8%B1%DA%A9%D8%A8
        serie_id example: 115791
        """
        print("Getting season id...")
        serie_id = self.get_movie_id()

        seasons_data = requests.get(SERIES_DATA.format(serie_id), headers=self.create_header()).json()["result"]["seasons"]

        for season_data in seasons_data:
            if season_data["seasonOrderId"] == str(self.season):
                print(f"Season id: {season_data['seasonId']}")
                return season_data["seasonId"]
        
        raise FindEpisodeError("There is no season or episode with these specifications.")

    def get_episode_id(self, id: int) -> int:
        print("Getting episode id...")
        episodes_id = requests.get(EPISODE_DATA.format(id), headers=self.create_header()).json()["result"]

        try: 
            return episodes_id[int(self.episode) - 1]["mediaId"]
        except:
            return episodes_id[0]["mediaId"]
        
        print("Episode id found")
    
    def get_movie_qualities_urls(self, id: int) -> str:
        print("Getting movie qualities urls")
        movie_detail = requests.get(MOVIE_DETAIL.format(id), headers=self.create_header()).json()

        self.movie_name = f"{self.get_latin_name(movie_detail).replace(' ', '')}-s{self.season}-e{self.episode}"

        movie_file = movie_detail["MediaInfoModel"]["FileFullName"]

        qualities_urls = requests.get(movie_file, headers=self.create_header()).text

        self.qualities = self.get_qualities(qualities_urls)

        print("Done")

        return qualities_urls

    def get_qualities(self, qualities_urls: str) -> list:
        """
        return qualities
        """
        print("Getting qualities")
        qualities = []

        for line in qualities_urls.split("\n"):
            if "RESOLUTION=" in line:
                qualities.append(line.split("RESOLUTION=")[1].split(",")[0].split("x")[1])
        print(f"Qualities: {qualities}")
        return qualities

    def is_serie(self):
        if "series" in self.movie_url:
            return True
        return False

    def get_latin_name(self, movie_detail) -> str:
        print("Getting movie name...")
        movie_attribute = movie_detail["PostTypeAttrValueModels"]
        
        for attr in movie_attribute:
            if attr["Key"] == "movie-latin-name":
                print(f"Movie name: {attr['Value']}")
                return attr["Value"]

    def get_url_by_quality(self, qualities_urls: str, quality: str) -> str:
        """
        return url
        """
        print("Getting movie url by quality")

        qualities_urls = qualities_urls.split("\n")

        for i, url in enumerate(qualities_urls):
            if quality in url:
                print(f"Found {quality} url")
                return qualities_urls[i + 1]

        raise FindEpisodeError("There is no quality or episode with these specifications.")

    def get_dubbing_languages(self, qualities_urls: str) -> list:
        """
        return dubbing languages
        """
        print("Getting dubbing languages")
        dubbing_languages = []

        for line in qualities_urls.split("\n"):
            if "TYPE=AUDIO" in line:
                print(line.split("LANGUAGE=")[1])
                dubbing_languages.append(line.split('LANGUAGE="')[1].split('"')[0])

        print("Done")

        return dubbing_languages

    def get_dubbing_sound_url_by_lang(self, qualities_urls: str, lang: str) -> str:
        """
        return url of dubbing sound
        """
        print("Getting dubbing files")
        for line in qualities_urls.split("\n"):
            if "TYPE=AUDIO" in line and lang in line:
                print(f"{lang} Dubbing Language found!")
                return line.split('URI="')[1].split('"')[0]

    def get_file_parts(self, file_url: str) -> str:
        """
        return movie parts
        """
        print("Getting file parts")
        request = requests.get(file_url).text

        file_parts = []

        for line in request.split("\n"):
            if "https://" in line:
                file_parts.append(line)

        encryption_url = file_parts[0].split('URI="')[1].split('"')[0]
        file_parts = file_parts[1:]

        print("Getting movie parts done")

        return encryption_url, file_parts

    def download_file(self, url: str, file_path: str) -> None:
        """
        download file from url and save it in file_name
        """
        print(f"Downloading {file_path}")
        with open(file_path, "wb") as file:
            file.write(requests.get(url).content)
        print(f"Downloaded {file_path}")

    def thread_download(self, urls: list, files_paths: list) -> None:
        """
        thread download file from url and save it in file_name
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            for url in urls:
                executor.submit(self.download_file, url, files_paths[urls.index(url)])

    def create_parts_list_file(self, movie_parts: list):
        print("Creating parts list file")
        with open("part_list.txt", "w") as file:
            for i in range(len(movie_parts)):
                file.write(f"file 'decrypted-{i+1}.ts'" + "\n")
        print("Done")

    def combine_parts(self, file_format) -> None:
        print(f"Combining {file_format} files...")
        command = f'cd "{pathlib.Path(__file__).parent.resolve()}" &&'

        if file_format == "mp4":
            command += f' ffmpeg -f concat -safe 0 -i part_list.txt -c copy "{self.movie_name}_video.mp4"'
        elif file_format == "mp3":
            command += f' ffmpeg -f concat -i part_list.txt -c copy "{self.movie_name}_audio.ts" && ffmpeg -i {self.movie_name}_audio.ts -vn {self.movie_name}_audio.wav'
        else:
            raise FileNotSupported("File format is not supported")

        os.system(command)
        print("Done")

    def add_audio_to_video(self) -> None:
        print("Adding audio to video...")

        command = f'cd "{pathlib.Path(__file__).parent.resolve()}" && ffmpeg -i {self.movie_name}_video.mp4 -i {self.movie_name}_audio.wav -map 0:v -map 1:a -c:v copy -shortest {self.movie_name}.mp4'
        os.system(command)
        print("Done")

    def delete_all_files(self, formats: list) -> None:
        print("Deleting files...")
        for file in os.listdir():
            for format in formats:
                if file.endswith(format):
                    os.remove(file)
        print("Done! Enjoy your movie!")


class Encryption:
    def __init__(self, encryption_file_key: str) -> None:
        self.encryption_file_key = open(encryption_file_key, 'rb').read()
    
    def ivof(self, x: int) -> bytes:
        res = bytearray(16)
        for i in range(1, 5):
            res[-i] = x & 255
            x >>= 8
        return bytes(res)

    def decrypt(self, encrypted_file_name: str) -> str:
        """
        return decrypted file name
        """
        print(f"Decrypting {encrypted_file_name}...")
        cipher = AES.new(self.encryption_file_key, AES.MODE_CBC, iv=self.ivof(int(encrypted_file_name.split("-")[1])))
        encrypted_file = open(encrypted_file_name, 'rb').read()
        p = cipher.decrypt(encrypted_file)
        with open(f"decrypted-{encrypted_file_name.split('-')[1]}.ts", 'wb') as file:
            file.write(p)
        
        print(f"Decrypted {encrypted_file_name}")


if __name__ == "__main__":


    parser = argparse.ArgumentParser(description="Download movie from namava.ir")

    parser.add_argument("movie_url", help="movie url")
    parser.add_argument("-s", "--season", help="season number", type=int, default=1)
    parser.add_argument("-e", "--episode", help="episode number(optional)", type=int)
    parser.add_argument("-q", "--quality", help="quality\nQualities: 152, 202, 270, 360, 480, 720, 1080", type=str, default="480")
    parser.add_argument("-d", "--dubbing", type=str)

    args = parser.parse_args()

    namava = Namava(movie_url=args.movie_url, season=args.season, episode=args.episode)
    namava.login(username=USERNAME, password=PASSWORD)

    if namava.has_subscription():

        if namava.is_serie():
            episode_id = namava.get_episode_id(namava.get_season_id())

            qualities_urls = namava.get_movie_qualities_urls(episode_id)

        else:
            qualities_urls = namava.get_movie_qualities_urls(namava.get_movie_id())

        namava.delete_all_files([".ts", ".txt", ".mp4", ".key"])

        movie_url = namava.get_url_by_quality(qualities_urls, args.quality)

        encryption_url, movie_parts = namava.get_file_parts(movie_url)

        namava.download_file(encryption_url, "encryption.key")

        namava.thread_download(movie_parts, [part.split("/")[-1].split("?")[0] for part in movie_parts])
        
        namava.create_parts_list_file(movie_parts)

        encryption = Encryption("encryption.key")

        for i, part in enumerate(movie_parts):
            encryption.decrypt(part.split("/")[-1].split("?")[0])

        namava.combine_parts("mp4")

        namava.delete_all_files([".ts", ".txt", ".key"])

        ## Download Dubbing
        sound_url = namava.get_dubbing_sound_url_by_lang(qualities_urls, args.dubbing)

        encryption_url, sound_parts = namava.get_file_parts(sound_url)

        namava.download_file(encryption_url, "encryption.key")

        namava.thread_download(sound_parts, [part.split("/")[-1].split("?")[0] for part in sound_parts])

        namava.create_parts_list_file(sound_parts)

        encryption = Encryption("encryption.key")

        for i, part in enumerate(sound_parts):
            encryption.decrypt(part.split("/")[-1].split("?")[0])
        
        namava.combine_parts("mp3")

        namava.add_audio_to_video()


        namava.delete_all_files([".ts", ".txt", ".key"])

    else:
        raise SubscriptionError("You don't have subscription!")