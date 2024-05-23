from typing import List, Tuple

from ..exceptions import ClientError, HashtagNotFound, MediaNotFound, ClientUnauthorizedError
from ..extractors import (
    extract_hashtag_gql,
    extract_hashtag_v1,
    extract_media_gql,
    extract_media_v1,
)
from ..types import Hashtag, Media

import time
import h_common as common

class HashtagMixin:
    """
    Helpers for managing Hashtag
    """

    def hashtag_info_a1(self, name: str, max_id: str = None) -> Hashtag:
        """
        Get information about a hashtag by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag

        max_id: str
            Max ID, default value is None

        Returns
        -------
        Hashtag
            An object of Hashtag
        """
        params = {"max_id": max_id} if max_id else None
        data = self.public_a1_request(f"/explore/tags/{name}/", params=params)
        if not data.get("hashtag"):
            raise HashtagNotFound(name=name, **data)
        return extract_hashtag_gql(data["hashtag"])

    def hashtag_info_gql(
        self, name: str, amount: int = 12, end_cursor: str = None
    ) -> Hashtag:
        """
        Get information about a hashtag by Public Graphql API

        Parameters
        ----------
        name: str
            Name of the hashtag

        amount: int, optional
            Maximum number of media to return, default is 12

        end_cursor: str, optional
            End Cursor, default value is None

        Returns
        -------
        Hashtag
            An object of Hashtag
        """
        variables = {"tag_name": name, "show_ranked": False, "first": int(amount)}
        if end_cursor:
            variables["after"] = end_cursor
        data = self.public_graphql_request(
            variables, query_hash="f92f56d47dc7a55b606908374b43a314"
        )
        if not data.get("hashtag"):
            raise HashtagNotFound(name=name, **data)
        # return extract_hashtag_gql(data["hashtag"])
        return data["hashtag"]

    def hashtag_info_v1(self, name: str) -> Hashtag:
        """
        Get information about a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag

        Returns
        -------
        Hashtag
            An object of Hashtag
        """
        result = self.private_request(f"tags/{name}/info/")
        return extract_hashtag_v1(result)

    def hashtag_info(self, name: str) -> Hashtag:
        """
        Get information about a hashtag

        Parameters
        ----------
        name: str
            Name of the hashtag

        Returns
        -------
        Hashtag
            An object of Hashtag
        """
        try:
            hashtag = self.hashtag_info_a1(name)
        except Exception:
            # Users do not understand the output of such information and create bug reports
            # such this - https://github.com/adw0rd/instagrapi/issues/364
            # if not isinstance(e, ClientError):
            #     self.logger.exception(e)
            hashtag = self.hashtag_info_v1(name)
        return hashtag

    def hashtag_related_hashtags(self, name: str) -> List[Hashtag]:
        """
        Get related hashtags from a hashtag

        Parameters
        ----------
        name: str
            Name of the hashtag

        Returns
        -------
        List[Hashtag]
            List of objects of Hashtag
        """
        data = self.public_a1_request(f"/explore/tags/{name}/")
        if not data.get("hashtag"):
            raise HashtagNotFound(name=name, **data)
        return [
            extract_hashtag_gql(item["node"])
            for item in data["hashtag"]["edge_hashtag_to_related_tags"]["edges"]
        ]

    def hashtag_medias_a1_chunk(
        self, name: str, user_id_set:set, caption_set:set,
        tab_key: str = "", end_cursor: str = None, check_spam:bool = True
    ) -> Tuple[List[Media], str]:
        """
        Get chunk of medias and end_cursor by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag
        [NOT USE]max_amount: int, optional
            Maximum number of media to return, default is 27
        user_id_set: set
            check exist user
        tab_key: str, optional
            Tab Key, default value is ""
        end_cursor: str, optional
            End Cursor, default value is None

        Returns
        -------
        Tuple[List[Media], str]
            List of objects of Media and end_cursor
            has_next_page:boolean
        """
        assert tab_key in (
            "edge_hashtag_to_top_posts",
            "edge_hashtag_to_media",
        ), 'You must specify one of the options for "tab_key" ("edge_hashtag_to_top_posts" or "edge_hashtag_to_media")'
        unique_set = set()
        medias = []
        while True:
            # data = self.public_a1_request(
            #     f"/explore/tags/{name}/",
            #     params={"max_id": end_cursor} if end_cursor else {},
            # )["hashtag"]
            data = self.hashtag_info_gql(name, amount=1000, end_cursor=end_cursor)
                
            page_info = data["edge_hashtag_to_media"]["page_info"]
            end_cursor = page_info["end_cursor"]
            has_next_page = page_info["has_next_page"] # True, False
            edges = data[tab_key]["edges"]
            print(f"get edge data : {len(edges)}")
            for edge in edges:
                media_pk = edge["node"]["id"]
                user_id = edge['node']['owner']['id'] # meida's owner id = user id
                
                # check uniq
                if media_pk in unique_set:
                    continue
                else:
                    unique_set.add(media_pk)
                    
                # check exist user id
                if user_id in user_id_set:
                    print(f"[PASS]exist user_id : {user_id}")
                    continue
                else:
                    user_id_set.add(user_id)
                
                # check caption
                if len(edge['node']['edge_media_to_caption']['edges']) != 0 and check_spam == True:
                    caption = str(edge['node']['edge_media_to_caption']['edges'][0]['node']['text'])
                    if caption != "":
                        if common.check_spam(caption, caption) == True:
                            continue
                    
                        # check exist caption
                        if caption in caption_set:
                            print(f"[PASS]exist caption : {user_id}")
                            continue
                
                # check contains hashtag in caption
                # media = extract_media_gql(edge["node"])
                # if f"#{name}" not in media.caption_text:
                #     continue
                # Enrich media: Full user, usertags and video_url
                while 1:
                    try:
                        media_res = self.media_info_gql(media_pk)
                        medias.append(media_res)
                        break
                    except MediaNotFound as e:
                        print()
                        print(f"hashtag.py -> hashtag_medias_a1_chunk() -> MediaNotFound")
                        print(f"continue next node")
                        print()
                        break
                    except ClientUnauthorizedError as e:
                        # change to new proxy
                        print()
                        print(f"[에러]ClientUnauthorizedError : 401 Client Error: Unauthorized for url")
                        new_proxy = common.get_rotate_proxy()
                        self.set_proxy(new_proxy)
                        print()
                        time.sleep(2)
            ######################################################
            # infinity loop in hashtag_medias_top_a1
            # https://github.com/adw0rd/instagrapi/issues/52
            ######################################################
            # Mikhail Andreev, [30.12.20 02:17]:
            # Instagram always returns the same 9 medias for top
            # I think we should return them without a loop
            ######################################################
            # if not page_info["has_next_page"] or not end_cursor:
            #     break
            # if max_amount and len(medias) >= max_amount:
            #     break
            break
        return medias, end_cursor, has_next_page

    def hashtag_medias_a1(
        self, name: str, amount: int = 27, tab_key: str = ""
    ) -> List[Media]:
        """
        Get medias for a hashtag by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 27
        tab_key: str, optional
            Tab Key, default value is ""

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        medias, _ = self.hashtag_medias_a1_chunk(name, amount, tab_key)
        if amount:
            medias = medias[:amount]
        return medias

    def hashtag_medias_v1_chunk(
        self, name: str, max_amount: int = 27, tab_key: str = "", max_id: str = None
    ) -> Tuple[List[Media], str]:
        """
        Get chunk of medias for a hashtag and max_id (cursor) by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        max_amount: int, optional
            Maximum number of media to return, default is 27
        tab_key: str, optional
            Tab Key, default value is ""
        max_id: str
            Max ID, default value is None

        Returns
        -------
        Tuple[List[Media], str]
            List of objects of Media and max_id
        """
        assert tab_key in (
            "top",
            "recent",
            "clips",
        ), 'You must specify one of the options for "tab_key" ("top", "recent", "clips")'
        data = {
            "media_recency_filter": "default",
            "tab": tab_key,
            "_uuid": self.uuid,
            "include_persistent": "false",
            "rank_token": self.rank_token,
        }

        medias = []
        while True:
            result = self.private_request(
                f"tags/{name}/sections/",
                params={"max_id": max_id} if max_id else {},
                data=self.with_default_data(data),
            )
            for section in result["sections"]:
                layout_content = section.get("layout_content") or {}
                nodes = layout_content.get("medias") or []
                for node in nodes:
                    if max_amount and len(medias) >= max_amount:
                        break
                    media = extract_media_v1(node["media"])
                    # check contains hashtag in caption
                    # if f"#{name}" not in media.caption_text:
                    #     continue
                    medias.append(media)
            if not result["more_available"]:
                break
            if max_amount and len(medias) >= max_amount:
                break
            max_id = result["next_max_id"]
        return medias, max_id

    def hashtag_medias_v1(
        self, name: str, amount: int = 27, tab_key: str = ""
    ) -> List[Media]:
        """
        Get medias for a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 27
        tab_key: str, optional
            Tab Key, default value is ""

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        medias, _ = self.hashtag_medias_v1_chunk(name, amount, tab_key)
        if amount:
            medias = medias[:amount]
        return medias

    def hashtag_medias_top_a1(self, name: str, amount: int = 9) -> List[Media]:
        """
        Get top medias for a hashtag by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 9

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return self.hashtag_medias_a1(name, amount, tab_key="edge_hashtag_to_top_posts")

    def hashtag_medias_top_v1(self, name: str, amount: int = 9) -> List[Media]:
        """
        Get top medias for a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 9

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return self.hashtag_medias_v1(name, amount, tab_key="top")

    def hashtag_medias_top(self, name: str, amount: int = 9) -> List[Media]:
        """
        Get top medias for a hashtag

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 9

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        try:
            medias = self.hashtag_medias_top_a1(name, amount)
        except ClientError:
            medias = self.hashtag_medias_top_v1(name, amount)
        return medias

    def hashtag_medias_recent_a1(self, name: str, amount: int = 71) -> List[Media]:
        """
        Get recent medias for a hashtag by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 71

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return self.hashtag_medias_a1(name, amount, tab_key="edge_hashtag_to_media")

    def hashtag_medias_recent_v1(self, name: str, amount: int = 27) -> List[Media]:
        """
        Get recent medias for a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 71

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return self.hashtag_medias_v1(name, amount, tab_key="recent")

    def hashtag_medias_recent(self, name: str, amount: int = 27) -> List[Media]:
        """
        Get recent medias for a hashtag

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 71

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        try:
            medias = self.hashtag_medias_recent_a1(name, amount)
        except ClientError:
            medias = self.hashtag_medias_recent_v1(name, amount)
        return medias

    def hashtag_medias_reels_v1(self, name: str, amount: int = 27) -> List[Media]:
        """
        Get reels medias for a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 71

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return self.hashtag_medias_v1(name, amount, tab_key="clips")

    def hashtag_follow(self, hashtag: str, unfollow: bool = False) -> bool:
        """
        Follow to hashtag
        Parameters
        ----------
        hashtag: str
            Unique identifier of a Hashtag
        unfollow: bool, optional
            Unfollow when True
        Returns
        -------
        bool
            A boolean value
        """
        assert self.user_id, "Login required"
        name = "unfollow" if unfollow else "follow"
        data = self.with_action_data({"user_id": self.user_id})
        result = self.private_request(
            f"web/tags/{name}/{hashtag}/", domain="www.instagram.com", data=data
        )
        return result["status"] == "ok"

    def hashtag_unfollow(self, hashtag: str) -> bool:
        """
        Unfollow to hashtag
        Parameters
        ----------
        hashtag: str
            Unique identifier of a Hashtag
        Returns
        -------
        bool
            A boolean value
        """
        return self.hashtag_follow(hashtag, unfollow=True)
