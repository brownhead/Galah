from inspect import getargspec
from warnings import warn
from copy import deepcopy
from bson import ObjectId
from bson.errors import InvalidId
from galah.db.models import *
import json
from collections import namedtuple

#: An anonymous admin user useful when accessing this module from the local
#: system.
admin_user = namedtuple("User", "account_type")("admin")
           
class APICall(object):
    """Wraps an API call and handles basic permissions along with providing a
    simple interface to get meta data on the API call.
    
    """
    
    __slots__ = ("wrapped_function", "allowed", "argspec", "name")
            
    class PermissionError(RuntimeError):
        def __init__(self, *args, **kwargs):
            RuntimeError.__init__(self, *args, **kwargs)
    
    def __init__(self, wrapped_function, allowed = None):
        #: The raw function we are wrapping that performs the actual logic.
        self.wrapped_function = wrapped_function
        
        #: The account types that are allowed to call this function, if None 
        #: any account type may call this function.
        self.allowed = allowed
        
        #: Information about the arguments this API call accepts in the same
        #: format :func: inspect.getargspec returns.
        self.argspec = getargspec(wrapped_function)
        
        #: The name of the wrapped function.
        self.name = wrapped_function.func_name
        
    def __call__(self, current_user, *args, **kwargs):
        arg_spec = getargspec(self.wrapped_function)
        
        # If no validation is required this won't actually be a problem, however
        # it's certainly not something that you should be doing.
        if not hasattr(current_user, "account_type"):
            # !! Purposely exceeds 80 character cap for formatting reason. Do
            #    not "fix."
            warn("current_user (%s) is not a valid user object." % repr(current_user))
        
        # Check if the current user has permisson to perform this operation
        if self.allowed and current_user.account_type not in self.allowed:
            raise APICall.PermissionError(
                "Only %s users are allowed to call %s" %
                    (
                        " or ".join(self.allowed),
                        self.wrapped_function.func_name
                    )
            )
        
        # Only pass the current user to the function if the function wants it
        if len(self.argspec[0]) != 0 and self.argspec[0][0] == "current_user":
            return str(self.wrapped_function(current_user, *args, **kwargs))
        else:
            return str(self.wrapped_function(*args, **kwargs))

def api_call(allowed = None):
    """Decorator that wraps a function with the :class: APICall class."""
    
    if isinstance(allowed, basestring):
        allowed = (allowed, )
    
    def wrapped(func):
        return APICall(func, allowed)
        
    return wrapped

## Some useful low level functions ##
def _get_user(email):
    try:
        return User.objects.get(email = email)
    except User.DoesNotExist:
        raise RuntimeError("User %s does not exist." % email)
        
def _get_class(query):
    try:
        # Check if the user provided a valid ObjectId
        return Class.objects.get(id = ObjectId(query))
    except Class.DoesNotExist:
        raise RuntimeError("Class with ID %s does not exist." % query)
    except InvalidId:
        pass

    matches = list(Class.objects(name__icontains = query))
    
    if not matches:
        raise RuntimeError("No classes matched your query of %s." % query)    
    elif len(matches) == 1:
        return matches[0]
    else:
        raise RuntimeError(
            "%d classes match your query of %s: %s. Refine your query and try "
            "again." % (
                len(matches),
                query, 
                ", ".join("%s (ID: %s)" % (i.name, i.id) for i in matches)
            )
        )
        
import datetime
def _to_datetime(time):
    try:
        return datetime.datetime(time)
    except TypeError:
        pass
        
    try:
        return datetime.datetime.strptime(time, "%m/%d/%Y %H:%M:%S")
    except (OverflowError, ValueError):
        raise ValueError(
            "Could not convert the %s into a time object." % repr(time)
        )
        
## Below are the actual API calls ##
@api_call()
def get_api_info():
    # This function should be memoized
    
    api_info = []
    for k, v in api_calls.items():
        api_info.append({"name": k})
        current = api_info[-1]
        
        # Loop through all the arguments the function takes in and add
        # information on each argument to the api_info
        current["args"] = []
        for i in xrange(len(v.argspec.args)):
            current["args"].append({"name": v.argspec.args[i]})
            
            if v.argspec.defaults:
                # The number of arguments without default values
                ndefaultless = len(v.argspec.args) - len(v.argspec.defaults)
                
                # If the current argument has a default value make note of it
                if ndefaultless <= i:
                    current["args"][-1].update({
                        "default_value": v.argspec.defaults[i - ndefaultless]
                    })
    
    return json.dumps(api_info, separators = (",", ":"))

from galah.db.crypto.passcrypt import serialize_seal, seal
from mongoengine import OperationError
@api_call("admin")
def create_user(email, password, account_type = "student",
                send_receipt = False):
    """Creates a user with the given credentials.
    
    :param email: The email the user will use to sign in.
    
    :param password: The users password, it will be immediately hashed (unless
                     **send_receipt** is True in which case it will send an
                     email to the user containing their password).

    :param account_type: The account type. Current available options are
                         student, teacher, or admin. Multiple account types are
                         not legal.

    :param send_receipt: If True the given email will be sent an email
                         containing their credentials.
    :type send_receipt: bool

    :raises RuntimeError: If the user could not be created.
    :raises SMTPException: If an email receipt could not be sent.
    
    """

    new_user = User(
        email = email, 
        seal = serialize_seal(seal(password)), 
        account_type = "student"
    )
    
    try:
        new_user.save(force_insert = True)
    except OperationError:
        raise RuntimeError("A user with that email already exists.")
    
    return "Successfully created a new %s user with email %s." % \
               (new_user.account_type, new_user.email)

@api_call("admin")
def delete_user(email):
    """Deletes a user with the given email. **This is irreversable.**

    :param email: The user-to-be-deleted's email.

    :raises RuntimeError: If the user could not be deleted

    """
    
    _get_user(email).delete()
        
    return "Successfully deleted user with %s." % email
    
@api_call(("admin", "teacher"))
def find_class(name_contains = ""):
    """Finds a class with the given fields.
    
    :param name_contains: A part of (or the whole) name of the class. Case
                          insensitive.
    
    :raises RuntimeError: If the database could not be queried.
                          
    """
    
    matches = Class.objects(name__icontains = name_contains)
    
    if not matches:
        return "No classes found with '%s' in their names." % name_contains
    else:
        return "%d match(es) found: %s." % (
            len(matches),
            ", ".join("%s (ID: %s)" % (i.name, i.id) for i in matches)
        )

@api_call(("admin", "teacher"))
def enroll_student(email, enroll_in):
    """Enrolls a student in a given class.

    :param email: The student's email.
    
    :param enroll_in: Part of the name (case-insensitive) or the  ID of the
                      class to enroll the student in.

    :raises RuntimeError: If the user could not be enrolled.

    """

    the_class = _get_class(enroll_in)
    
    user = _get_user(email)
    
    if the_class.id in user.classes:
        raise RuntimeError("User %s is already enrolled in %s (ID: %s)." %
            (user.email, the_class.name, the_class.id))
            
    user.classes.append(the_class.id)
    user.save()
    
    return "Successfully enrolled %s in %s (ID: %s)." % (
        user.email, the_class.name, the_class.id
    )

@api_call(("admin", "teacher"))
def drop_student(email, drop_from):
    """Drops a student (or dis-enrolls) a student from a given class.

    :param email: The student's email.

    :param drop_from: The ID of the class to drop the student from.

    :returns: None

    :raises RuntimeError: If the student could not be dropped.

    """
    
    the_class = _get_class(drop_from)

    user = _get_user(email)
        
    if drop_from not in user.classes:
        raise RuntimeError("User %s is not enrolled in %s (ID: %s)" %
            (email, the_class.name, drop_from))
    
    user.classes.remove(drop_from)
    user.save()
    
    return "Successfully dropped %s from %s (ID: %s)." % (
        email, the_class.name, drop_from
    )

@api_call("admin")
def create_class(name):
    """Creates a class with the given name.

    :param name: The name of the class to create.
    :type name: str

    :returns: The newly created class object.

    :raises RuntimeError: If the class could not be created.

    """

    new_class = Class(name = name)
    new_class.save()
    
    return "Successfully created new class %s (ID: %s)" % (
        new_class.name, new_class.id
    )

@api_call("admin")
def delete_class(to_delete):
    """Deletes a class.

    :param id: The ID of the class to delete.
    :type id: bson.ObjectId

    :returns: None

    :raises RuntimeError: If the class could not be deleted.

    """

    the_class = _get_class(to_delete)
        
    # Delete all the assignments for the class
    assignments = list(Assignment.objects(for_class = the_class.id))
    for i in assignments:
        i.remove()
        
    the_class.remove()
    
    return "Successfully deleted class %s (ID: %s) and all of its " \
           "assignments." % (the_class.name, the_class.id)

@api_call(("admin", "teacher"))
def create_assignment(name, due, for_class):
    """Creates an assignment.

    :param name: The name of the assignment.

    :param due: The due date of the assignmet, ex: "10/20/2012 10:09:00".

    :param for_class: The ID of the class the assignment is for.

    :returns: The newly created assignment.

    :raises RuntimeError: If the asssignment could not be created.

    """

    due = _to_datetime(due)

    the_class = _get_class(for_class)

    new_assignment = Assignment(name = name, due = due,
                                for_class = the_class.id)
    new_assignment.save()
    
    return "Successfully created new assignment %s (due: %s, for_class: %s, " \
           "ID: %s)." % (
        new_assignments.name,
        new_assignment.due.strftime("%m/%d/%Y %H:%M:%S"),
        new_assignment.for_class,
        new_assignment.id
    )

@api_call(("admin", "teacher"))
def delete_assignment(id):
    """Deletes an assignment.

    :param id: The ID of the assignment to delete.

    :returns: None

    :raises RuntimeError: If the assignment could not be deleted.

    """

    Assignment.objects.get(id = ObjectId(id)).remove()
    
    return "Successfully deleted assignment with ID '%s'." % str(id)

import threading
import Queue
tar_tasks_queue = Queue.Queue()
tar_tasks_thread = None

# Copied from web.views._upload_submission.SUBMISSION_DIRECTORY. Adding a new
# submission should be transformed into an API call and _upload_submissions
# should use that API call, but this will work for now.
SUBMISSION_DIRECTORY = "/var/local/galah.web/submissions/"

import tempfile
import os
import subprocess
def tar_tasks():
    # The thread that executes this function should execute as a daemon,
    # therefore there is no reason to allow an explicit exit. It will be 
    # brutally killed once the app exits.
    while True:
        # Block until we get a new task.
        task = tar_tasks_queue.get()

        # Find any expired archives and remove them
        Archive.objects(expires__lt = datetime.datetime.today()).delete()

        # Create a temporary directory we will create our archive in
        temp_directory = tempfile.mkdtemp()
        
        # We're going to create a list of file we need to put in the archive
        files = [os.path.join(temp_directory, "meta.json")]

        # Serialize the meta data and throw it into a file
        json.dump(task[1], open(files[0], "w"))

        for i in task[1]["submissions"]:
            sym_path = os.path.join(temp_directory, i["id"])
            os.symlink(os.path.join(SUBMISSION_DIRECTORY, i["id"]), sym_path)
            files.append(sym_path)



        archive_file = tempfile.mkstemp(suffix = ".tar.gz")[1]

        # Run tar and do the actual archiving. Will block until it's finished.
        return_code = subprocess.call(
            [
                "tar", "--dereference", "--create", "--gzip", "--directory",
                temp_directory, "--file", archive_file
            ] + [os.path.relpath(i, temp_directory) for i in files]
        )

        # Make the results available in the database
        archive = Archive.objects.get(id = ObjectId(task[0]))
        if return_code != 0:
            archive.error_string = \
                "tar failed with error code %d." % return_code
        else:
            archive.file_location = archive_file

        archive.expires = \
            datetime.datetime.today() + datetime.timedelta(hours = 2)

        archive.save()
        

@api_call(("admin", "teacher"))
def get_submissions(current_user, assignment, email = None):
    """Creates an archive of students' submissions that a teacher or admin
    can download.
    
    :param assignment: The assignment that the retrieved submissions will be
                       for.
    :param email: The user that the retrieved submissions will be created by.
                 If none, all user's who submitted for the given assignment
                 will be retrieved.

    """
    
    query = {"assignment": ObjectId(assignment)}
    
    # If we were to always add user to the query, then mongo would search for
    # documents with email == None in the case that email equals None, which is
    # not desirable.
    if email:
        query["email"] = email
    
    submissions = list(Submission.objects(marked_for_grading = True, **query))
    
    if not submissions:
        return "No submissions found."

    # Form meta data on each submission that we will soon convert to JSON and
    # put inside of the archive we will send the user.
    submissions_meta = [
        {"id": str(i.id), "user": i.user, "timestamp": str(i.timestamp)}
            for i in submissions
    ]

    meta_data = {
        "query": {"assignment": assignment, "email": email},
        "submissions": submissions_meta
    }

    # Create a new entry in the database so we can track the progress of the
    # job.
    new_archive = Archive(requester = current_user.email)
    new_archive.save(force_insert = True)

    # Determine how many jobs are ahead of this one before we put it in the
    # queue.
    current_jobs = tar_tasks_queue.qsize()

    # We will not perform the work of archiving right now but will instead pass
    # if off to another thread to take care of it.
    tar_tasks_queue.put((new_archive.id, meta_data))

    # If the thread responsible for archiving is not running, start it up.
    global tar_tasks_thread
    if tar_tasks_thread is None or not tar_tasks_thread.is_alive():
        tar_tasks_thread = threading.Thread(name = "tar_tasks", target = tar_tasks)
        tar_tasks_thread.start()

    return ("Creating archive with id [%s]. Approximately %d jobs ahead of "
            "you. Access your archive by trying "
            "[Galah Domain]/archives/%s"
                % (str(new_archive.id), current_jobs, str(new_archive.id)))



api_calls = dict((k, v) for k, v in globals().items() if isinstance(v, APICall))

if __name__ == "__main__":
    import json
    print get_api_info("current_user")
