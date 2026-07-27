from ums.utils import resolve_msisdn_from_request


def fetch_msisdn(request):
    return {"msisdn": resolve_msisdn_from_request(request)}
