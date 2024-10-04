from typing import List, Tuple

from ..exceptions import ClientError, HashtagNotFound, MediaNotFound, ClientUnauthorizedError, UserNotFound, ClientNotFoundError
from ..extractors import (
    extract_hashtag_gql,
    extract_hashtag_v1,
    extract_media_gql,
    extract_media_v1,
)
from ..types import Hashtag, Media

import time
import h_common as common
import MyDataClass
from concurrent import futures

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

    def hashtag_medias_a1_chunk(self, 
        name: str, user_id_set:set, caption_set:set, old_media_id_set:set,
        end_cursor: str = None, check_spam:bool = True, check_caption:bool = True
    ) -> Tuple[MyDataClass.HashTagInfo, List[MyDataClass.MediaDetailInfo]]:
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
        Tuple[MyDataClass.HashTagInfo, List[MyDataClass.MediaDetailInfo]]
            An object of HashTagInfo and List of objects of MediaDetailInfo
        """
        
        
        def fetch_hashtag_user_info(shortcode:str):
            return_data = {}
            
            while True:
                try:
                    cl = common.get_random_client()
                    cl.set_proxy(common.get_rotate_proxy())
                    media_res = cl.media_info_gql2(shortcode)
                    mediaDetailInfo = MyDataClass.MediaDetailInfo.convertInstaResponse(media_res)
                    
                    return_data["media"] = mediaDetailInfo.dict()
                except MediaNotFound as e:
                    print(f"hashtag.py -> hashtag_medias_a1_chunk() -> MediaNotFound")
                    return None
                except ClientUnauthorizedError as e:
                    # change to new proxy
                    print(f"[에러]ClientUnauthorizedError : 401 Client Error: Unauthorized for url")
                    cl.set_proxy(common.get_rotate_proxy())
                    continue
                except Exception as e:
                    print(f"[media ERROR]fetch_hashtag_user_info() : {e}")
                    continue
                
                # get user info
                while True:
                    try:
                        cl.set_proxy(common.get_rotate_proxy(free_mode=True))
                        result = cl.user_info_by_username_gql2(mediaDetailInfo.username)
                        if result is None:
                            # print(f"can't find user : {mediaDetailInfo.username} - try get new username form userid")
                            return None
                        
                        userInfoObj = MyDataClass.InstaUser.convertInstaResponse(result)
                        return_data["insta_user"] = userInfoObj.dict()
                        
                        if check_spam is True:
                            if common.check_spam(None, userInfoObj.biography) == True:
                                return None
                        if userInfoObj.avg_like_count < 1:
                            return None
                        
                        # 최종 데이터 반환
                        return return_data
                    except (UserNotFound, ClientNotFoundError) as e:
                        print(f"can't find user : {mediaDetailInfo.username}")
                        return None
                    except KeyError as e: # 특정인 대상으로 일어남 이유 모름 graphql 키가 없음으로 나옴 해당 유저는 지워야 함.
                        print(f"{e} - KeyError user : {mediaDetailInfo.username}")
                        return None
                    except Exception as e:
                        print(f"[isnta_user ERROR]user_info_by_username_gql2() : {e}")
                        del cl
                        cl = common.get_random_client()
                        cl.set_proxy(common.get_rotate_proxy(free_mode=True))
                        continue
                
        
        # assert tab_key in (
        #     "edge_hashtag_to_top_posts",
        #     "edge_hashtag_to_media",
        # ), 'You must specify one of the options for "tab_key" ("edge_hashtag_to_top_posts" or "edge_hashtag_to_media")'
        
        mediaDetailInfo_results = []
        # data = self.public_a1_request(
        #     f"/explore/tags/{name}/",
        #     params={"max_id": end_cursor} if end_cursor else {},
        # )["hashtag"]
        data = self.hashtag_info_gql(name, amount=1000, end_cursor=end_cursor)
        
        hashTagInfo = MyDataClass.HashTagInfo.convertInstaResponse(data)
        
        edges_recent = data['edge_hashtag_to_media']["edges"] # 최신 게시물
        edges_top = data['edge_hashtag_to_top_posts']["edges"] # 인기 게시물
        edges = edges_top + edges_recent
        
        print(f"get recent[{len(edges_recent)}] + top edge data[{len(edges_top)}] : {len(edges)}")
        
        # check exist user
        work_media_list = []
        for edge in edges:
            mediaShortInfo = MyDataClass.MediaShortInfo.convertInstaResponse(edge)
            
            media_pk = mediaShortInfo.media_id
            shortcode = mediaShortInfo.shortcode
            user_id = mediaShortInfo.userid
            caption = mediaShortInfo.caption
            
            # check media_pk is uniq
            if media_pk in old_media_id_set:
                continue
            else:
                old_media_id_set.add(media_pk)
                
            # check exist user id
            if user_id in user_id_set:
                print(f"[PASS]exist user_id : {user_id}")
                continue
            else:
                user_id_set.add(user_id)
            
            # check caption
            if check_caption is True and caption != None and caption != "":
                # check exist caption
                if caption in caption_set:
                    print(f"[PASS]exist caption : {user_id}")
                    continue
            # check spam
            if check_spam is True:
                if common.check_spam(caption, None) is True:
                    continue
                    
            # work list add   
            work_media_list.append(shortcode)
        
        if len(work_media_list) != 0:
            results = []
            with futures.ThreadPoolExecutor(max_workers = len(work_media_list)) as executor:
                print()
                print(f"max worker : {executor._max_workers}")
                print()
                # start Thread work
                try:
                    for shortcode in work_media_list:
                        # get media info
                        t = executor.submit(fetch_hashtag_user_info, shortcode)
                        results.append(t)
                        
                        # for stop delay
                        time.sleep(0.5)
                except KeyboardInterrupt as e:
                    print(f"KeyboardInterrupt : cancel by user")
                    
                # wait for running tasks
                executor.shutdown(wait=True)
                
            # put return media data
            for f in futures.as_completed(results):
                out = f.result()
                if out is not None:
                    mediaDetailInfo_results.append(out)
            
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
        
        return hashTagInfo, mediaDetailInfo_results

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
