from .views import is_supervisor

def supervisor_flag(request):
    return {'is_supervisor': is_supervisor(request.user) if request.user.is_authenticated else False}
