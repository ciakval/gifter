from django.utils.cache import add_never_cache_headers


class SignedInNoStoreMiddleware:
    """Send Cache-Control private, no-store on every response to a signed-in user.

    Family phones and tablets are shared. Without this, the back button or the browser cache
    could show the previous person's pages, which carry claims, to the next person after a
    sign-out (Pitfall 24). Signed-out public pages keep their normal caching.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            add_never_cache_headers(response)
        return response
