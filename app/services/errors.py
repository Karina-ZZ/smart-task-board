class WorkflowError(Exception):
    """Base class for workflow-level business failures."""


class EntityNotFoundError(WorkflowError):
    """A required business entity does not exist."""


class PermissionDeniedError(WorkflowError):
    """The actor is not permitted to perform the requested operation."""


class AuthenticationFailedError(WorkflowError):
    """External identity could not be verified for sign-in."""


class IdentityBindingRequiredError(WorkflowError):
    """A verified external identity is not bound to an active local employee."""


class ExternalIdentityUnavailableError(WorkflowError):
    """The configured external identity provider is temporarily unavailable."""


class InvalidStateTransitionError(WorkflowError):
    """The aggregate is not in a state accepted by the operation."""


class TaskVersionConflictError(WorkflowError):
    """The command was based on an obsolete task version."""


class BusinessValidationError(WorkflowError):
    """Business facts supplied to an operation are invalid."""


class DependencyNotSatisfiedError(WorkflowError):
    """A task node cannot start because a predecessor is incomplete."""


class DependencyCycleError(WorkflowError):
    """The task node dependency graph contains a directed cycle."""


class OpenTaskIssueConflictError(WorkflowError):
    """An active or unclosed task issue prevents the requested action."""
