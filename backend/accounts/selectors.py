"""Read-side queries over users (§14.2)."""

from .models import User


def assignable_lawyers():
    """Everyone a case may be handed to — the single definition of "assignable" (§5.1, §7.2).

    Both the dropdown source (`/lawyers/`) and the write boundary (`AssignableLawyerField`) read
    it, so the list a lawyer is offered can never disagree with the list the API accepts.
    """
    return User.objects.filter(is_deleted=False, is_active=True).order_by("username")
