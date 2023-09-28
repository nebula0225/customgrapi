import logging
from urllib.parse import urlparse

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from .mixins.account import AccountMixin
from .mixins.album import DownloadAlbumMixin, UploadAlbumMixin
from .mixins.auth import LoginMixin
from .mixins.bloks import BloksMixin
from .mixins.challenge import ChallengeResolveMixin
from .mixins.clip import DownloadClipMixin, UploadClipMixin
from .mixins.collection import CollectionMixin
from .mixins.comment import CommentMixin
from .mixins.direct import DirectMixin
from .mixins.explore import ExploreMixin
from .mixins.fbsearch import FbSearchMixin
from .mixins.fundraiser import FundraiserMixin
from .mixins.hashtag import HashtagMixin
from .mixins.highlight import HighlightMixin
from .mixins.igtv import DownloadIGTVMixin, UploadIGTVMixin
from .mixins.insights import InsightsMixin
from .mixins.location import LocationMixin
from .mixins.media import MediaMixin
from .mixins.multiple_accounts import MultipleAccountsMixin
from .mixins.note import NoteMixin
from .mixins.notification import NotificationMixin
from .mixins.password import PasswordMixin
from .mixins.photo import DownloadPhotoMixin, UploadPhotoMixin
from .mixins.private import PrivateRequestMixin
from .mixins.public import (
    ProfilePublicMixin,
    PublicRequestMixin,
    TopSearchesPublicMixin,
)
from .mixins.share import ShareMixin
from .mixins.story import StoryMixin
from .mixins.timeline import ReelsMixin
from .mixins.totp import TOTPMixin
from .mixins.track import TrackMixin
from .mixins.user import UserMixin
from .mixins.video import DownloadVideoMixin, UploadVideoMixin

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Used as fallback logger if another is not provided.
DEFAULT_LOGGER = logging.getLogger("instagrapi")


class Client(
    PublicRequestMixin,
    ChallengeResolveMixin,
    PrivateRequestMixin,
    TopSearchesPublicMixin,
    ProfilePublicMixin,
    LoginMixin,
    ShareMixin,
    TrackMixin,
    FbSearchMixin,
    HighlightMixin,
    DownloadPhotoMixin,
    UploadPhotoMixin,
    DownloadVideoMixin,
    UploadVideoMixin,
    DownloadAlbumMixin,
    NotificationMixin,
    UploadAlbumMixin,
    DownloadIGTVMixin,
    UploadIGTVMixin,
    MediaMixin,
    UserMixin,
    InsightsMixin,
    CollectionMixin,
    AccountMixin,
    DirectMixin,
    LocationMixin,
    HashtagMixin,
    CommentMixin,
    StoryMixin,
    PasswordMixin,
    DownloadClipMixin,
    UploadClipMixin,
    ReelsMixin,
    ExploreMixin,
    BloksMixin,
    TOTPMixin,
    MultipleAccountsMixin,
    NoteMixin,
    FundraiserMixin,
):
    proxy = None

    def __init__(
        self,
        settings: dict = {},
        proxy: str = None,
        delay_range: list = None,
        logger=DEFAULT_LOGGER,
        **kwargs,
    ):

        super().__init__(**kwargs)

        self.settings = settings
        self.logger = logger
        self.delay_range = delay_range

        self.set_proxy(proxy)

        self.init()

    def set_proxy(self, dsn: str):
        if dsn:
            assert isinstance(
                dsn, str
            ), f'Proxy must been string (URL), but now "{dsn}" ({type(dsn)})'
            self.proxy = dsn
            proxy_href = "{scheme}{href}".format(
                scheme="http://" if not urlparse(self.proxy).scheme else "",
                href=self.proxy,
            )
            self.public.proxies = self.private.proxies = {
                "http": proxy_href,
                "https": proxy_href,
            }
            return True
        self.public.proxies = self.private.proxies = {}
        return False
