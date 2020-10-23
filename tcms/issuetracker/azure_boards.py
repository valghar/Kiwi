# -*- coding: utf-8 -*-
from requests.auth import HTTPBasicAuth
import requests

from tcms.core.contrib.linkreference.models import LinkReference
from tcms.issuetracker.base import IssueTrackerType, IntegrationThread


class AzureAPI():
    """
        Azure Boards API interaction class.

    """
    def __init__(self, base_url=None, password=None):
        self.api_version = "?api-version=6.0"
        self.headers = {"Accept": 'application/json-patch+json',
                        'Content-type': 'application/json-patch+json'}
        self.auth = HTTPBasicAuth('apikey', password)
        self.base_url = base_url + "/_apis/"

    def get_issue(self, issue_id):
        url = "{0}{1}{2}{3}".format(self.base_url, "wit/workitems/",
                                    issue_id, self.api_version)
        return self._request("GET", url, headers=self.headers, auth=self.auth)

    def create_issue(self, body):
        url = "{0}{1}{2}".format(self.base_url, "wit/workitems/$Issue", self.api_version)
        return self._request("POST", url, headers=self.headers, auth=self.auth, json=body)

    def update_issue(self, issue_id, body):
        url = "{0}{1}{2}{3}".format(self.base_url, "wit/workitems/",
                                    issue_id, self.api_version)
        return self._request("PATCH", url, headers=self.headers, auth=self.auth, json=body)

    def get_comments(self, issue_id):
        headers = {"Content-type": "application/json"}
        url = "{0}{1}{2}{3}{4}{5}".format(self.base_url, "wit/workitems/",
                                          issue_id, "/comments", self.api_version,
                                          "-preview.3")
        return self._request("GET", url, headers=headers, auth=self.auth)

    def add_comment(self, issue_id, body):
        headers = {"Content-type": "application/json"}
        url = "{0}{1}{2}{3}{4}{5}".format(self.base_url, "wit/workitems/",
                                          issue_id, "/comments", self.api_version,
                                          "-preview.3")
        return self._request("POST", url, headers=headers, auth=self.auth, json=body)

    @staticmethod
    def _request(method, url, **kwargs):
        return requests.request(method, url, **kwargs).json()


class AzureThread(IntegrationThread):
    """
        Execute AzureBoards code in a thread!

        Executed from the IssueTracker interface methods.
    """
    def post_comment(self):
        # NOTE: Posting comment is in preview state in API v6.0.
        # Line endings have to be converted to HTML <br/>.
        # https://docs.microsoft.com/en-us/azure/devops/boards/work-items/work-item-template-examples?view=azure-devops#add-guidance-in-a-rich-text-field
        comment_body = {
                "text": self.text().replace("\n", "<br/>")
            }
        self.rpc.add_comment(self.bug_id, comment_body)


class AzureBoards(IssueTrackerType):
    """
        Support for AzureBoards. Requires:

        :base_url: - URL to a AzureBoards project for which we're going to report issues
        e.g. https://dev.azure.com/{organization}/{project}
        :api_password: - AzureBoards API token - needs required permissions

        .. note::

            You can leave the ``api_url`` and ``api_username`` fields blank because
            the integration code doesn't use them!
    """
    it_class = AzureThread

    def _rpc_connection(self):
        # NOTE: we use an access token so only the password field is required
        return AzureAPI(self.bug_system.base_url, self.bug_system.api_password)

    def is_adding_testcase_to_issue_disabled(self):
        return not (self.bug_system.base_url and self.bug_system.api_password)

    def report_issue_from_testexecution(self, execution, user):
        """
            AzureBoards creates the Work Item with Title
        """

        create_body = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "from": "null",
                "value": 'Failed test: %s' % execution.case.summary,
            }]

        update_body = [
            {
                "op": "replace",
                "path": "/fields/System.Description",
                "from": "null",
                # Line endings have to be converted to HTML <br/>.
                # https://docs.microsoft.com/en-us/azure/devops/boards/work-items/work-item-template-examples?view=azure-devops#add-guidance-in-a-rich-text-field
                "value": self._report_comment(execution).replace("\n", "<br/>")
            }]

        try:
            issue = self.rpc.create_issue(create_body)
            self.rpc.update_issue(issue['id'], update_body)

            issue_url = self.bug_system.base_url + "/_workitems/edit/" + str(issue['id'])
            # add a link reference that will be shown in the UI
            LinkReference.objects.get_or_create(
                execution=execution,
                url=issue_url,
                is_defect=True,
            )

            return issue_url
        except Exception:  # pylint: disable=broad-except
            # something above didn't work so return a link for manually
            # entering issue details with info pre-filled
            url = self.bug_system.base_url
            if not url.endswith('/'):
                url += '/'

            return url + '_workitems/create/Issue'

    def details(self, url):
        """
            Return issue details from Azure Board
        """
        issue = self.rpc.get_issue(self.bug_id_from_url(url))
        return {
            'title': issue['fields']['System.Title'],
            'description': issue['fields']['System.Description'],
        }
