#!/usr/bin/env python
from oic.oauth2.message import AuthorizationRequest
from oic.utils import jwt

__author__ = 'rohe0002'

# ========================================================================

import time
import socket

from oic.oic.message import factory as msgfactory, OpenIDRequest
from oictest.check import *
# Used upstream not in this module so don't remove
from oictest.opfunc import *
from oic.oic.consumer import Consumer

# ========================================================================

class Request():
    request = ""
    method = ""
    lax = False
    request_args= {}
    kw_args = {}
    tests = {"post": [CheckHTTPResponse], "pre":[]}

    def __init__(self):
        pass

    #noinspection PyUnusedLocal
    def __call__(self, environ, trace, location, response, content, features):
        _client = environ["client"]
        if isinstance(self.request, basestring):
            request = msgfactory(self.request)
        else:
            request = self.request

        try:
            kwargs = self.kw_args.copy()
        except KeyError:
            kwargs = {}

        try:
            kwargs["request_args"] = self.request_args.copy()
            _req = kwargs["request_args"].copy()
        except KeyError:
            _req = {}

        if request in [OpenIDRequest, AuthorizationRequest]:
            if "use_nonce" in features and features["use_nonce"]:
                if not "nonce" in kwargs:
                    _nonce = "dummy_nonce"
                    try:
                        kwargs["request_args"]["nonce"] = _nonce
                    except KeyError:
                        kwargs["request_args"] = {"nonce": _nonce}

                    _client.nonce = _nonce

        cis = getattr(_client, "construct_%s" % request.__name__)(request,
                                                                  **kwargs)

        try:
            cis.lax = self.lax
        except AttributeError:
            pass

        ht_add = None

        if "authn_method" in kwargs:
            h_arg = _client.init_authentication_method(cis, **kwargs)
        else:
            h_arg = None

        url, body, ht_args, cis = _client.uri_and_body(request, cis,
                                                      method=self.method,
                                                      request_args=_req)

        environ["cis"].append(cis)
        if h_arg:
            ht_args.update(h_arg)
        if ht_add:
            ht_args.update({"headers": ht_add})

        if trace:
            trace.request("URL: %s" % url)
            trace.request("BODY: %s" % body)
            try:
                trace.request("HEADERS: %s" % ht_args["headers"])
            except KeyError:
                pass

        response = _client.http_request(url, method=self.method,
                                            data=body, **ht_args)

        if trace:
            trace.reply("RESPONSE: %s" % response)
            trace.reply("CONTENT: %s" % response.text)
            trace.reply("COOKIES: %s" % response.cookies)
            try:
                trace.reply("HeaderCookies: %s" % response.headers["set-cookie"])
            except KeyError:
                pass

        return url, response, response.text

    def update(self, dic):
        _tmp = {"request": self.request_args, "kw": self.kw_args}
        for key, val in self.rec_update(_tmp, dic).items():
            setattr(self, "%s_args" % key, val)

    def rec_update(self, dic0, dic1):
        res = {}
        for key, val in dic0.items():
            if key not in dic1:
                res[key] = val
            else:
                if isinstance(val, dict):
                    res[key] = self.rec_update(val, dic1[key])
                else:
                    res[key] = dic1[key]

        for key, val in dic1.items():
            if key in dic0:
                continue
            else:
                res[key] = val

        return res

class GetRequest(Request):
    method = "GET"

class MissingResponseType(GetRequest):
    request = "AuthorizationRequest"
    request_args = {"response_type": []}
    lax = True
    tests = {"post": [CheckRedirectErrorResponse]}

class AuthorizationRequestCode(GetRequest):
    request = "AuthorizationRequest"
    request_args= {"response_type": ["code"]}

class AuthorizationRequestCode_WQC(GetRequest):
    request = "AuthorizationRequest"
    request_args= {"response_type": ["code"],
                   "query": "component"}
    tests = {"pre": [CheckResponseType],
             "post": [CheckHTTPResponse]}

class AuthorizationRequestCode_RUWQC(GetRequest):
    request = "AuthorizationRequest"
    request_args= {"response_type": ["code"],
            "redirect_uri": "https://smultron.catalogix.se/authz_cb?foo=bar"}
    tests = {"pre": [CheckResponseType],
             "post": [CheckHTTPResponse]}

    def __call__(self, environ, trace, location, response, content, features):
        _client = environ["client"]
        base_url = _client.redirect_uris[0]
        self.request_args["redirect_uri"] = base_url + "?foo=bar"
        return Request.__call__(self, environ, trace, location, response,
                                content, features)

class AuthorizationRequest_Mismatching_Redirect_uri(GetRequest):
    request = "AuthorizationRequest"
    request_args= {"response_type": ["code"],
                   "redirect_uri": "https://hallon.catalogix.se/authz_cb"}
    tests = {"pre": [CheckResponseType],
             "post": [CheckErrorResponse]}

class AuthorizationRequest_with_nonce(GetRequest):
    request = "AuthorizationRequest"
    request_args= {"response_type": ["code"],
                   "nonce": "12nonce34"}

class OpenIDRequestCode(GetRequest):
    request = "OpenIDRequest"
    request_args = {"response_type": ["code"], "scope": ["openid"]}
    tests = {"pre": [CheckResponseType],"post": [CheckHTTPResponse]}

class ConnectionVerify(GetRequest):
    request = "OpenIDRequest"
    request_args = {"response_type": ["code"],
                    "scope": ["openid"]}
    tests = {"pre": [CheckResponseType],"post": [CheckHTTPResponse]}
    interaction_check = True

class OpenIDRequestCodeWithNonce(GetRequest):
    request = "OpenIDRequest"
    request_args = {"response_type": ["code"], "scope": ["openid"],
                    "nonce": "12nonce34"}
    tests = {"pre": [CheckResponseType],"post": [CheckHTTPResponse]}

class OpenIDRequestCodeDisplayPage(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["display"] = "page"

class OpenIDRequestCodeDisplayPopUp(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["display"] = "popup"

class OpenIDRequestCodePromptNone(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["prompt"] = "none"
        self.tests["post"] = [VerifyErrResponse]

class OpenIDRequestCodePromptNoneWithIdToken(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["prompt"] = "none"
        self.tests["post"] = [VerifyErrResponse]

    def __call__(self, environ, trace, location, response, content, features):
        _client = environ["client"]

        return PostRequest.__call__(self, environ, trace, location, response,
                                    content, features)

class OpenIDRequestCodePromptNoneWithUserID(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["prompt"] = "none"
        self.tests["post"] = [VerifyErrResponse]

    def __call__(self, environ, trace, location, response, content, features):
        _id_token = environ["response_message"]["id_token"]
        jso = json.loads(jwt.unpack(_id_token)[1])
        user_id = jso["user_id"]
        self.request_args["idtoken_claims"] = {"user_id": {"value": user_id}}

        return OpenIDRequestCode.__call__(self, environ, trace, location,
                                          response, content, features)

class OpenIDRequestCodePromptLogin(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["prompt"] = "login"


class OpenIDRequestCodeScopeProfile(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["scope"].append("profile")

class OpenIDRequestCodeScopeEMail(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["scope"].append("email")

class OpenIDRequestCodeScopeAddress(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["scope"].append("address")

class OpenIDRequestCodeScopePhone(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["scope"].append("phone")

class OpenIDRequestCodeScopeAll(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["scope"].extend(["phone", "address", "email",
                                           "profile"])

class OpenIDRequestCodeUIClaim1(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["userinfo_claims"] = {"claims": {"name": None}}


class OpenIDRequestCodeUIClaim2(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        # Picture and email optional
        self.request_args["userinfo_claims"] = {"claims": {"picture": None,
                                                           "email": None}}

class OpenIDRequestCodeUIClaim3(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        # Must name, may picture and email
        self.request_args["userinfo_claims"] = {"claims": {
                                                "name": {"essential": True},
                                                "picture": None,
                                                "email": None}}

class OpenIDRequestCodeIDTClaim1(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        # Must auth_time
        self.request_args["idtoken_claims"] = {"claims": {
                                                "auth_time": {"essential": True}}}

class OpenIDRequestCodeIDTClaim2(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["idtoken_claims"] = {"claims": {"acr": {"values":
                                                                      ["2"]}}}

class OpenIDRequestCodeIDTClaim3(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        # Must acr
        self.request_args["idtoken_claims"] = {"claims": {
                                                    "acr": {"essential": True}}}

class OpenIDRequestCodeIDTMaxAge1(OpenIDRequestCode):

    def __init__(self):
        time.sleep(2)
        OpenIDRequestCode.__init__(self)
        self.request_args["idtoken_claims"] = {"max_age": 1}

class OpenIDRequestCodeIDTMaxAge10(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["idtoken_claims"] = {"max_age": 10}

class OpenIDRequestToken(GetRequest):
    request = "OpenIDRequest"
    request_args = {"response_type": ["token"], "scope": ["openid"]}
    tests = {"pre": [CheckResponseType],"post": [CheckHTTPResponse]}

class OpenIDRequestIDToken(GetRequest):
    request = "OpenIDRequest"
    request_args = {"response_type": ["id_token"], "scope": ["openid"]}
    tests = {"pre": [CheckResponseType],"post": [CheckHTTPResponse]}

class OpenIDRequestCodeToken(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["response_type"].append("token")

class OpenIDRequestCodeIDToken(OpenIDRequestCode):

    def __init__(self):
        OpenIDRequestCode.__init__(self)
        self.request_args["response_type"].append("id_token")

class OpenIDRequestIDTokenToken(OpenIDRequestIDToken):

    def __init__(self):
        OpenIDRequestIDToken.__init__(self)
        self.request_args["response_type"].append("token")

class OpenIDRequestCodeIDTokenToken(OpenIDRequestCodeIDToken):

    def __init__(self):
        OpenIDRequestCodeIDToken.__init__(self)
        self.request_args["response_type"].append("token")

class PostRequest(Request):
    method = "POST"

class RegistrationRequest(PostRequest):
    request = "RegistrationRequest"

    def __init__(self):
        PostRequest.__init__(self)

        self.request_args = {"type": "client_associate",
                             "redirect_uris": ["https://example.com/authz_cb"],
                             "contact": ["roland@example.com"],
                             "application_type": "web",
                             "application_name": "OIC test tool"}

        self.tests["post"].append(RegistrationInfo)

class RegistrationRequest_WQC(PostRequest):
    """ With query component """
    request = "RegistrationRequest"

    def __init__(self):
        PostRequest.__init__(self)

        self.request_args = {"type": "client_associate",
                    "redirect_uris": ["https://example.com/authz_cb?foo=bar"],
                    "contact": ["roland@example.com"],
                    "application_type": "web",
                    "application_name": "OIC test tool"}

        self.tests["post"].append(RegistrationInfo)

from oictest import start_key_server

class RegistrationRequest_WF(PostRequest):
    """ With fragment, which is not allowed """
    request = "RegistrationRequest"
    tests = {"post": [CheckErrorResponse]}

    def __init__(self):
        PostRequest.__init__(self)

        self.request_args = {"type": "client_associate",
                     "redirect_uris": ["https://example.com/authz_cb#foobar"],
                     "contact": ["roland@example.com"],
                     "application_type": "web",
                     "application_name": "OIC test tool"}


from oictest import KEY_EXPORT_ARGS

class RegistrationRequest_KeyExp(PostRequest):
    """ Registration request with client key export """
    request = "RegistrationRequest"

    def __init__(self):
        PostRequest.__init__(self)

        self.request_args = {"type": "client_associate",
                             "redirect_uris": ["https://example.com/authz_cb"],
                             "contact": ["roland@example.com"],
                             "application_type": "web",
                             "application_name": "OIC test tool"}

        self.export_server = "http://%s:8090/export" % socket.gethostname()

    def __call__(self, environ, trace, location, response, content, features):
        _client = environ["client"]
        part, res = _client.keystore.key_export(self.export_server,
                                                **KEY_EXPORT_ARGS)

        # Do the redirect_uris dynamically
        self.request_args["redirect_uris"] = _client.redirect_uris

        for name, url in res.items():
            self.request_args[name] = url

        if "keyprovider" not in environ:
            _pop = start_key_server(part)
            environ["keyprovider"] = _pop
            trace.info("Started key provider")
            time.sleep(1)

        return PostRequest.__call__(self, environ, trace, location, response,
                              content, features)

class RegistrationRequest_update(PostRequest):
    """ With query component """
    request = "RegistrationRequest"

    def __init__(self):
        PostRequest.__init__(self)

        self.request_args = {"type": "client_update",
                             "contact": ["roland@example.com",
                                         "roland@example.org"]}

        self.tests["post"].append(RegistrationInfo)

    def __call__(self, environ, trace, location, response, content, features):
        _client = environ["client"]

        self.request_args["client_secret"] = _client.get_client_secret()
        self.request_args["client_id"] = _client.client_id

        return PostRequest.__call__(self, environ, trace, location, response,
                                    content, features)

class RegistrationRequest_rotate_secret(PostRequest):
    """ With query component """
    request = "RegistrationRequest"

    def __init__(self):
        PostRequest.__init__(self)

        self.request_args = {"type": "rotate_secret"}

    def __call__(self, environ, trace, location, response, content, features):
        _client = environ["client"]

        self.request_args["client_secret"] = _client.get_client_secret()
        self.request_args["client_id"] = _client.client_id

        return PostRequest.__call__(self, environ, trace, location, response,
                                    content, features)

class AccessTokenRequest(PostRequest):
    request = "AccessTokenRequest"

    def __init__(self):
        PostRequest.__init__(self)
        #self.kw_args = {"authn_method": "client_secret_basic"}

    def __call__(self, environ, trace, location, response, content, features):
        if "authn_method" not in self.kw_args:
            _pinfo = environ["provider_info"]
            if "token_endpoint_auth_types_supported" in _pinfo:
                for meth in ["client_secret_basic", "client_secret_post",
                             "client_secret_jwt", "private_key_jwt"]:
                    if meth in _pinfo["token_endpoint_auth_types_supported"]:
                        self.kw_args = {"authn_method": meth}
                        break
            else:
                self.kw_args = {"authn_method": "client_secret_basic"}
        return Request.__call__(self, environ, trace, location, response,
                              content, features)
        
        
class AccessTokenRequestCSPost(AccessTokenRequest):

    def __init__(self):
        PostRequest.__init__(self)
        self.kw_args = {"authn_method": "client_secret_post"}

class AccessTokenRequestCSJWT(AccessTokenRequest):
    tests = {"pre": [CheckKeys]}

    def __init__(self):
        PostRequest.__init__(self)
        self.kw_args = {"authn_method": "client_secret_jwt"}

class AccessTokenRequestPKJWT(AccessTokenRequest):
    tests = {"pre": [CheckKeys]}

    def __init__(self):
        PostRequest.__init__(self)
        self.kw_args = {"authn_method": "private_key_jwt"}

class AccessTokenRequest_err(AccessTokenRequest):

    def __init__(self):
        PostRequest.__init__(self)
        self.tests["post"]=[]

class UserInfoRequestGetBearerHeader(GetRequest):
    request = "UserInfoRequest"

    def __init__(self):
        GetRequest.__init__(self)
        self.kw_args = {"authn_method": "bearer_header"}

class UserInfoRequestGetBearerHeader_err(GetRequest):
    request = "UserInfoRequest"

    def __init__(self):
        GetRequest.__init__(self)
        self.kw_args = {"authn_method": "bearer_header"}
        self.tests["post"]=[CheckErrorResponse]

class UserInfoRequestPostBearerHeader(PostRequest):
    request = "UserInfoRequest"

    def __init__(self):
        PostRequest.__init__(self)
        self.kw_args = {"authn_method": "bearer_header"}

class UserInfoRequestPostBearerBody(PostRequest):
    request = "UserInfoRequest"

    def __init__(self):
        PostRequest.__init__(self)
        self.kw_args = {"authn_method": "bearer_body"}

# -----------------------------------------------------------------------------

class Response():
    response = ""
    tests = {}

    def __init__(self):
        pass

    def __call__(self, environ, response):
        pass

class UrlResponse(Response):
    where = "url"
    type = "urlencoded"

class AuthzResponse(UrlResponse):
    response = "AuthorizationResponse"
    tests = {"post": [CheckAuthorizationResponse]}

class AuthzErrResponse(UrlResponse):
    response = "AuthorizationErrorResponse"
    #tests = {"post": [LoginRequired]}

#class RedirectedErrorResponse(UrlResponse):
#    response = "AuthorizationErrorResponse"
#    tests = {"post": [InvalidRequest]}

class BodyResponse(Response):
    where = "body"
    type = "json"

class RegistrationResponseCARS(BodyResponse):
    response = "RegistrationResponseCARS"

    def __call__(self, environ, response):
        _client = environ["client"]
        _client.keystore.remove_key_type("hmac")
        for prop in ["client_id", "client_secret"]:
            try:
                setattr(_client, prop, response[prop])
            except KeyError:
                pass

class RegistrationResponseCU(BodyResponse):
    response = "RegistrationResponseCU"

    def __call__(self, environ, response):
        _client = environ["client"]
        for prop in ["client_id"]:
            try:
                setattr(_client, prop, response[prop])
            except KeyError:
                pass

class AccessTokenResponse(BodyResponse):
    response = "AccessTokenResponse"

    def __init__(self):
        BodyResponse.__init__(self)
        self.tests = {"post": [VerifyAccessTokenResponse]}

class UserinfoResponse(BodyResponse):
    response = "OpenIDSchema"

    def __init__(self):
        BodyResponse.__init__(self)
        self.tests = {"post": [ScopeWithClaims]}

class CheckIdResponse(BodyResponse):
    response = "IdToken"

class ProviderConfigurationResponse(BodyResponse):
    response = "ProviderConfigurationResponse"

class ClientRegistrationErrorResponse(BodyResponse):
    response = "ClientRegistrationErrorResponse"

class AuthorizationErrorResponse(BodyResponse):
    response = "AuthorizationErrorResponse"

class ErrorResponse(BodyResponse):
    response = "ErrorResponse"

# ----------------------------------------------------------------------------
class DResponse(object):
    def __init__(self, status, type):
        self.content_type = type
        self.status = status

    def __getattr__(self, item):
        if item == "content-type":
            return self.content_type


#noinspection PyUnusedLocal
def discover(self, client, orig_response, content, issuer, location,
             features, _trace_):
    pcr = client.provider_config(issuer)
    _trace_.info("%s" % client.keystore._store)
    return "", DResponse(200, "application/json"), pcr


class Discover(Operation):
    tests = {"post": [ProviderConfigurationInfo]}
    function = discover
    environ_param = "provider_info"

    def post_op(self, result, environ, args):
        # Update the environ with the provider information
        # This overwrites what's there before. In some cases this might not
        # be preferable.

        environ[self.environ_param].update(result[2].to_dict())

# ===========================================================================

PHASES= {
    "login": (AuthorizationRequestCode, AuthzResponse),
    #"login-nonce": (AuthorizationRequest_with_nonce, AuthzResponse),
    "login-wqc": (AuthorizationRequestCode_WQC, AuthzResponse),
    "login-ruwqc": (AuthorizationRequestCode_RUWQC, AuthzResponse),
    "login-redirect-fault": (AuthorizationRequest_Mismatching_Redirect_uri,
                             AuthorizationErrorResponse),
    "verify": (ConnectionVerify, AuthzResponse),
    "oic-login": (OpenIDRequestCode, AuthzResponse),
    #"oic-login-nonce": (OpenIDRequestCodeWithNonce, AuthzResponse),
    "oic-login+profile": (OpenIDRequestCodeScopeProfile, AuthzResponse),
    "oic-login+email": (OpenIDRequestCodeScopeEMail, AuthzResponse),
    "oic-login+phone": (OpenIDRequestCodeScopePhone, AuthzResponse),
    "oic-login+address": (OpenIDRequestCodeScopeAddress, AuthzResponse),
    "oic-login+all": (OpenIDRequestCodeScopeAll, AuthzResponse),
    "oic-login+spec1": (OpenIDRequestCodeUIClaim1, AuthzResponse),
    "oic-login+spec2": (OpenIDRequestCodeUIClaim2, AuthzResponse),
    "oic-login+spec3": (OpenIDRequestCodeUIClaim3, AuthzResponse),

    "oic-login+idtc1": (OpenIDRequestCodeIDTClaim1, AuthzResponse),
    "oic-login+idtc2": (OpenIDRequestCodeIDTClaim2, AuthzResponse),
    "oic-login+idtc3": (OpenIDRequestCodeIDTClaim3, AuthzResponse),
    "oic-login+idtc4": (OpenIDRequestCodeIDTMaxAge1, AuthzResponse),
    "oic-login+idtc5": (OpenIDRequestCodeIDTMaxAge10, AuthzResponse),

    "oic-login+disp_page": (OpenIDRequestCodeDisplayPage, AuthzResponse),
    "oic-login+disp_popup": (OpenIDRequestCodeDisplayPopUp, AuthzResponse),

    "oic-login+prompt_none": (OpenIDRequestCodePromptNone, AuthzErrResponse),
    "oic-login+prompt_login": (OpenIDRequestCodePromptLogin, AuthzResponse),
    "oic-login+prompt_none+idtoken": (OpenIDRequestCodePromptNoneWithIdToken,
                                      AuthzErrResponse),
    "oic-login+prompt_none+request":(OpenIDRequestCodePromptNoneWithUserID,
                                     AuthzErrResponse),

    "oic-login-token": (OpenIDRequestToken, AuthzResponse),
    "oic-login-idtoken": (OpenIDRequestIDToken, AuthzResponse),
    "oic-login-code+token": (OpenIDRequestCodeToken, AuthzResponse),
    "oic-login-code+idtoken": (OpenIDRequestCodeIDToken, AuthzResponse),
    "oic-login-idtoken+token": (OpenIDRequestIDTokenToken, AuthzResponse),
    "oic-login-code+idtoken+token": (OpenIDRequestCodeIDTokenToken,
                                     AuthzResponse),
#
    "access-token-request_csp":(AccessTokenRequestCSPost,
                                  AccessTokenResponse),
    "access-token-request":(AccessTokenRequest, AccessTokenResponse),
    "access-token-request_csj":(AccessTokenRequestCSJWT,
                                  AccessTokenResponse),
    "access-token-request_pkj":(AccessTokenRequestPKJWT,
                                AccessTokenResponse),
    "access-token-request_err" : (AccessTokenRequest_err, ErrorResponse),
    "user-info-request":(UserInfoRequestGetBearerHeader, UserinfoResponse),
    "user-info-request_pbh":(UserInfoRequestPostBearerHeader, UserinfoResponse),
    "user-info-request_pbb":(UserInfoRequestPostBearerBody, UserinfoResponse),
    "user-info-request_err":(UserInfoRequestGetBearerHeader_err,
                             ErrorResponse),
    "oic-registration": (RegistrationRequest, RegistrationResponseCARS),
    "oic-registration-wqc": (RegistrationRequest_WQC, RegistrationResponseCARS),
    "oic-registration-wf": (RegistrationRequest_WF,
                            ClientRegistrationErrorResponse),
    "oic-registration-ke": (RegistrationRequest_KeyExp, RegistrationResponseCARS),
    "oic-registration-update": (RegistrationRequest_update,
                                RegistrationResponseCU),
    "oic-registration-rotate": (RegistrationRequest_rotate_secret,
                                RegistrationResponseCARS),
    "provider-discovery": (Discover, ProviderConfigurationResponse),
    "oic-missing_response_type": (MissingResponseType, AuthzErrResponse)
}

OWNER_OPS = []

FLOWS = {
    'oic-verify': {
        "name": 'Special flow used to find necessary user interactions',
        "descr": ('Request with response_type=code'),
        "sequence": ["verify"],
        "endpoints": ["authorization_endpoint"],
        "block": "key_export"
    },

    # -------------------------------------------------------------------------
    'oic-code-token': {
        "name": 'Simple authorization grant flow',
        "descr": ("1) Request with response_type=code",
                  "scope = ['openid']",
                  "2) AccessTokenRequest",
                  "Authentication method used is 'client_secret_post'"),
        "depends": ['mj-01'],
        "sequence": ["oic-login", "access-token-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
#    'oic-code+nonce-token': {
#        "name": 'Simple authorization grant flow',
#        "descr": ("1) Request with response_type=code",
#                  "scope = ['openid']",
#                  "2) AccessTokenRequest",
#                  "Authentication method used is 'client_secret_post'"),
#        "depends": ['mj-01'],
#        "sequence": ["oic-login-nonce", "access-token-request"],
#        "endpoints": ["authorization_endpoint", "token_endpoint"],
#        },
    'oic-code+token-token': {
        "name": "Flow with response_type='code token'",
        "descr": ("1) Request with response_type='code token'",
                  "2) AccessTokenRequest",
                  "Authentication method used is 'client_secret_post'"),
        "depends": ['mj-04'],
        "sequence": ["oic-login-code+token", "access-token-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
    'oic-code+idtoken-token': {
        "name": "Flow with response_type='code idtoken'",
        "descr": ("1) Request with response_type='code id_token'",
                  "2) AccessTokenRequest",
                  "Authentication method used is 'client_secret_post'"),
        "depends": ['mj-05'],
        "sequence": ["oic-login-code+idtoken", "access-token-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
    'oic-code+idtoken+token-token': {
        "name": "Flow with response_type='code token idtoken'",
        "descr": ("1) Request with response_type='code id_token token'",
                  "2) AccessTokenRequest",
                  "Authentication method used is 'client_secret_post'"),
        "depends": ['mj-07'],
        "sequence": ["oic-login-code+idtoken+token", "access-token-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
    # -------------------------------------------------------------------------

    'oic-token-userinfo': {
        "name": 'Implicit flow and Userinfo request',
        "descr": ("1) Request with response_type='token'",
                  "2) UserinfoRequest",
                  "  'bearer_body' authentication used"),
        "depends": ['mj-02'],
        "sequence": ['oic-login-token', "user-info-request"],
        "endpoints": ["authorization_endpoint", "userinfo_endpoint"],
        },
    'oic-code+token-userinfo': {
        "name": "Flow with response_type='code token' and Userinfo request",
        "descr": ("1) Request with response_type='code token'",
                  "2) UserinfoRequest",
                  "  'bearer_body' authentication used"),
        "depends": ['mj-04'],
        "sequence": ['oic-login-code+token', "user-info-request"],
        "endpoints": ["authorization_endpoint", "userinfo_endpoint"],
        },
    'oic-code+idtoken-token-userinfo': {
        "name": "Flow with response_type='code idtoken' and Userinfo request",
        "descr": ("1) Request with response_type='code id_token'",
                  "2) UserinfoRequest",
                  "  'bearer_body' authentication used"),
        "depends": ['oic-code+idtoken-token'],
        "sequence": ['oic-login-code+idtoken', "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'oic-idtoken+token-userinfo': {
        "name": "Flow with response_type='token idtoken' and Userinfo request",
        "descr": ("1) Request with response_type='id_token token'",
                  "2) UserinfoRequest",
                  "  'bearer_body' authentication used"),
        "depends": ['mj-06'],
        "sequence": ['oic-login-idtoken+token', "user-info-request"],
        "endpoints": ["authorization_endpoint", "userinfo_endpoint"],
        },
    'oic-code+idtoken+token-userinfo': {
        "name": """Flow with response_type='code idtoken token' and Userinfo
    request""",
        "descr": ("1) Request with response_type='code id_token token'",
                  "2) UserinfoRequest",
                  "  'bearer_body' authentication used"),
        "depends":["mj-07"],
        "sequence": ['oic-login-code+idtoken+token', "user-info-request"],
        "endpoints": ["authorization_endpoint", "userinfo_endpoint"],
        },
    'oic-code+idtoken+token-token-userinfo': {
        "name": """Flow with response_type='code idtoken token'
    grab a second token using the code and then do a Userinfo
    request""",
        "descr": ("1) Request with response_type='code id_token token'",
                  "2) AccessTokenRequest",
                  "  Authentication method used is 'client_secret_post'",
                  "3) UserinfoRequest",
                  "  'bearer_body' authentication used"),
        "depends": ['oic-code+idtoken+token-token'],
        "sequence": ["oic-login-code+idtoken+token", "access-token-request",
                     'user-info-request'],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },

    # -------------------------------------------------------------------------
    # beared body authentication
    'oic-code-token-userinfo_bb': {
        "name": """Authorization grant flow response_type='code token',
    UserInfo request using POST and bearer body authentication""",
        "descr": ("1) Request with response_type='code'",
                  "2) AccessTokenRequest",
                  "  Authentication method used is 'client_secret_post'",
                  "3) UserinfoRequest",
                  "  'bearer_body' authentication used"),
        "depends": ['oic-code-token'],
        "sequence": ["oic-login", "access-token-request",
                     "user-info-request_pbb"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'oic-token-userinfo_bb': {
        "name": """Implicit flow, UserInfo request using POST and bearer body
    authentication""",
        "descr": ("1) Request with response_type='token'",
                  "2) UserinfoRequest",
                  "  'bearer_body' authentication used"),
        "depends": ['mj-02'],
        "sequence": ['oic-login-token', "user-info-request_pbb"],
        "endpoints": ["authorization_endpoint", "userinfo_endpoint"],
        },
    'mj-00': {
        "name": 'Client registration Request',
        "sequence": ["oic-registration"],
        "endpoints": ["registration_endpoint"]
    },
    'mj-01': {
        "name": 'Request with response_type=code',
        "sequence": ["oic-login"],
        "endpoints": ["authorization_endpoint"]
    },
#    'mj-01n': {
#        "name": 'Request with response_type=code',
#        "sequence": ["oic-login-nonce"],
#        "endpoints": ["authorization_endpoint"]
#    },
    'mj-02': {
        "name": 'Request with response_type=token',
        "sequence": ["oic-login-token"],
        "endpoints": ["authorization_endpoint"]
    },
    'mj-03': {
        "name": 'Request with response_type=id_token',
        "sequence": ["oic-login-idtoken"],
        "endpoints": ["authorization_endpoint"]
    },
    'mj-04': {
        "name": 'Request with response_type=code token',
        "sequence": ["oic-login-code+token"],
        "endpoints": ["authorization_endpoint"],
        },
    'mj-05': {
        "name": 'Request with response_type=code id_token',
        "sequence": ['oic-login-code+idtoken'],
        "endpoints": ["authorization_endpoint"],
        },
    'mj-06': {
        "name": 'Request with response_type=id_token token',
        "sequence": ['oic-login-idtoken+token'],
        "endpoints": ["authorization_endpoint"],
        },
    'mj-07': {
        "name": 'Request with response_type=code id_token token',
        "sequence": ['oic-login-code+idtoken+token'],
        "endpoints": ["authorization_endpoint",],
        },
    # -------------------------------------------------------------------------
    'mj-11': {
        "name": 'UserInfo Endpoint Access with GET and bearer_header',
        "sequence": ["oic-login", "access-token-request", "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-12': {
        "name": 'UserInfo Endpoint Access with POST and bearer_header',
        "sequence": ["oic-login", "access-token-request",
                     "user-info-request_pbh"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-13': {
        "name": 'UserInfo Endpoint Access with POST and bearer_body',
        "sequence": ["oic-login", "access-token-request",
                     "user-info-request_pbb"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    # -------------------------------------------------------------------------
    'mj-14': {
        "name": 'Scope Requesting profile Claims',
        "sequence": ["oic-login+profile", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-15': {
        "name": 'Scope Requesting email Claims',
        "sequence": ["oic-login+email", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-16': {
        "name": 'Scope Requesting address Claims',
        "sequence": ["oic-login+address", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-17': {
        "name": 'Scope Requesting phone Claims',
        "sequence": ["oic-login+phone", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-18': {
        "name": 'Scope Requesting all Claims',
        "sequence": ["oic-login+all", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-19': {
        "name": 'OpenID Request Object with Required name Claim',
        "sequence": ["oic-login+spec1", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-20': {
        "name": 'OpenID Request Object with Optional email and picture Claim',
        "sequence": ["oic-login+spec2", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-21': {
        "name": ('OpenID Request Object with Required name and Optional email and picture Claim'),
        "sequence": ["oic-login+spec3", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        },
    'mj-22': {
        "name": 'Requesting ID Token with auth_time Claim',
        "sequence": ["oic-login+idtc1", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        "tests": [("verify-id-token", {"claims":{"auth_time": None}})]
        },
    'mj-23': {
        "name": 'Requesting ID Token with Required acr Claim',
        "sequence": ["oic-login+idtc2", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        "tests": [("verify-id-token", {"claims":{"acr": {"values": ["2"]}}})]
        },
    'mj-24': {
        "name": 'Requesting ID Token with Optional acr Claim',
        "sequence": ["oic-login+idtc3", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        "tests": [("verify-id-token", {"claims":{"acr": None}})]
        },
    'mj-25a': {
        "name": 'Requesting ID Token with max_age=1 seconds Restriction',
        "sequence": ["oic-login", "access-token-request",
                     "user-info-request", "oic-login+idtc4",
                     "access-token-request", "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        "tests": [("multiple-sign-on", {})]
        },
    'mj-25b': {
        "name": 'Requesting ID Token with max_age=10 seconds Restriction',
        "sequence": ["oic-login", "access-token-request",
                     "user-info-request", "oic-login+idtc5",
                     "access-token-request", "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        "tests": [("single-sign-on", {})]
    },
    # ---------------------------------------------------------------------
    'mj-26': {
        "name": 'Request with display=page',
        "sequence": ["oic-login+disp_page", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
    'mj-27': {
        "name": 'Request with display=popup',
        "sequence": ["oic-login+disp_popup", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
    'mj-28': {
        "name": 'Request with prompt=none',
        "sequence": ["oic-login+prompt_none"],
        "endpoints": ["authorization_endpoint"],
        "tests":[("verify-error", {"error":["login_required",
                                            "interaction_required",
                                            "session_selection_required",
                                            "consent_required"]})]
        },
    'mj-29': {
        "name": 'Request with prompt=login',
        "sequence": ["oic-login+prompt_login", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
    # ---------------------------------------------------------------------
    'mj-30': {
        "name": 'Access token request with client_secret_basic authentication',
        "sequence": ["oic-login", "access-token-request_csp"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
    'mj-31': {
        "name": 'Request with response_type=code and extra query component',
        "sequence": ["login-wqc"],
        "endpoints": ["authorization_endpoint"]
    },
    'mj-32': {
        "name": 'Request with redirect_uri with query component',
        "sequence": ["login-ruwqc"],
        "endpoints": ["authorization_endpoint"],
        "tests": [("verify-redirect_uri-query_component",
                {"redirect_uri":
                     PHASES["login-ruwqc"][0].request_args["redirect_uri"]})]
    },
    'mj-33': {
        "name": 'Registration where a redirect_uri has a query component',
        "sequence": ["oic-registration-wqc"],
        "endpoints": ["registration_endpoint"],
    },
    'mj-34': {
        "name": 'Registration where a redirect_uri has a fragment',
        "sequence": ["oic-registration-wf"],
        "endpoints": ["registration_endpoint"],
        },
    'mj-35': {
        "name": "Authorization request missing the 'response_type' parameter",
        "sequence": ["oic-missing_response_type"],
        "endpoints": ["authorization_endpoint"],
        "tests":[("verify-error", {"error":["invalid_request"]})]
    },
    'mj-36': {
        "name": "The sent redirect_uri does not match the registered",
        "sequence": ["login-redirect-fault"],
        "endpoints": ["authorization_endpoint"]
    },
    'mj-37': {
        "name": 'Access token request with client_secret_jwt authentication',
        "sequence": ["oic-registration-ke", "oic-login",
                     "access-token-request_csj"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
    'mj-38': {
        "name": 'Access token request with public_key_jwt authentication',
        "sequence": ["oic-registration-ke", "oic-login",
                     "access-token-request_pkj"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        },
    'mj-39': {
        "name": 'Trying to use access code twice should result in an error',
        "sequence": ["oic-login", "access-token-request",
                     "access-token-request_err"],
        "endpoints": ["authorization_endpoint", "token_endpoint"],
        "tests": [("verify-bad-request-response", {})],
        "depends":["oic-code-token"],
    },
    'mj-40': {
        "name": 'Trying to use access code twice should result in '
                'revoking previous issued tokens',
        "sequence": ["oic-login", "access-token-request",
                     "access-token-request_err", "user-info-request_err"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        "tests": [("verify-bad-request-response", {})],
        "depends":["mj-39"],
    },
    'mj-41': {
        "name": 'Registration and later registration update',
        "sequence": ["oic-registration", "oic-registration-update"],
        "endpoints": ["registration_endpoint"],
        },
    'mj-42': {
        "name": 'Registration and later secret rotate',
        "sequence": ["oic-registration", "oic-registration-rotate"],
        "endpoints": ["registration_endpoint"],
        "tests": [("changed-client-secret", {})],
        },
#    "mj-43": {
#        "name": 'using prompt=none with user hint through IdToken',
#        "sequence": ["oic-login", "access-token-request",
#                     "oic-login+prompt_none+idtoken"],
#        "endpoints": ["registration_endpoint"],
#        },
#    "mj-44": {
#        "name": 'using prompt=none with user hint through user_id in request',
#        "sequence": ["oic-login", "access-token-request",
#                     "oic-login+prompt_none+request"],
#        "endpoints": ["registration_endpoint"],
#        },
}

NEW = {
    'x-30': {
        "name": 'Scope Requesting profile Claims with aggregated Claims',
        "sequence": ["oic-login+profile", "access-token-request",
                     "user-info-request"],
        "endpoints": ["authorization_endpoint", "token_endpoint",
                      "userinfo_endpoint"],
        "tests": [("unpack-aggregated-claims", {})]

    },
}

if __name__ == "__main__":
    for name, spec in FLOWS.items():
        try:
            for dep in spec["depends"]:
                try:
                    assert dep in FLOWS
                except AssertionError:
                    print "%s missing in FLOWS" % dep
                    raise
        except KeyError:
            pass
        for op in spec["sequence"]:
            try:
                assert op in PHASES
            except AssertionError:
                print "%s missing in PHASES" % op
                raise