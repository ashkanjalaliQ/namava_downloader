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
        request = requests.post(LOGIN_URL, data={"UserName": username, "Password": password}).json()

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
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.98 Safari/537.36",
            "cookie": 'guest_token=' + self.token + '; anonymous_login=true; rb_guest_token=' + self.token + '; rb_anonymous_login=true; auth_v2=' + self.token + '; auth_token=; webengage=true; notification=true; dv-v3={"g":"desktop","platform":null}; _gid=GA1.2.1573384437.1640363012; _clck=1f4u8if|1|exj|0; profileId=13397249; content_viewed=17753; _ga_TLHYT3BK0M=GS1.1.1640376375.10.1.1640379177.0; _ga=GA1.2.884584504.1639002317; _clsk=pp9yw6|1640379178991|21|0|www.clarity.ms/eus2/collect;'
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

        seasons_data = requests.get(SERIES_DATA.format(serie_id)).json()["result"]["seasons"]

        for season_data in seasons_data:
            if season_data["seasonOrderId"] == str(self.season):
                print(f"Season id: {season_data['seasonId']}")
                return season_data["seasonId"]
        
        raise FindEpisodeError("There is no season or episode with these specifications.")

    def get_episode_id(self, id: int) -> int:
        print("Getting episode id...")
        episodes_id = requests.get(EPISODE_DATA.format(id), headers=self.create_header()).json()["result"]
        print(f"Episode id: {episodes_id}")
        return episodes_id[self.episode - 1]["mediaId"]
        

    def get_movie_qualities_urls(self, id: int) -> str:
        print("Getting movie qualities urls")
        movie_detail = requests.get(MOVIE_DETAIL.format(id), headers=self.create_header()).json()

        self.movie_name = self.get_latin_name(movie_detail)

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

    def get_movie_parts(self, movie_url: str) -> str:
        """
        return movie parts
        """
        print("Getting movie parts")
        request = requests.get(movie_url).text

        movie_parts = []

        for line in request.split("\n"):
            if "https://" in line:
                movie_parts.append(line)

        encryption_url = movie_parts[0].split('URI="')[1].split('"')[0]
        movie_parts = movie_parts[1:]

        print("Getting movie parts done")

        return encryption_url, movie_parts

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
        with open("movie_list.txt", "w") as file:
            for i in range(len(movie_parts)):
                file.write(f"file 'decrypted-{i+1}.ts'" + "\n")
        print("Done")

    def combine_video_files(self) -> None:
        print("Combining video files...")
        command = f'cd "{pathlib.Path(__file__).parent.resolve()}" && ffmpeg -f concat -safe 0 -i movie_list.txt -c copy "{self.movie_name.replace(" ", "")}.mp4"'
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

        url = namava.get_url_by_quality(qualities_urls, args.quality)
        encryption_url, movie_parts = namava.get_movie_parts(url)

        namava.download_file(encryption_url, "encryption.key")

        namava.thread_download(movie_parts, [part.split("/")[-1].split("?")[0] for part in movie_parts])
        
        namava.create_parts_list_file(movie_parts)

        encryption = Encryption("encryption.key")

        for i, part in enumerate(movie_parts):
            encryption.decrypt(part.split("/")[-1].split("?")[0])

        namava.combine_video_files()

        namava.delete_all_files([".ts", ".txt", ".key"])

    else:
        raise SubscriptionError("You don't have subscription!")