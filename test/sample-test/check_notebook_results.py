# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import utils

from kfp import Client


_RUN_LIST_PAGE_SIZE = 1000
_TEST_TIMEOUT = 1200

class NoteBookChecker(object):
    def __init__(self, testname, result, exit_code,
                 experiment=None, namespace='kubeflow'):
        """ Util class for checking notebook sample test running results.

        :param testname: test name in the json xml.
        :param result: name of the file that stores the test result
        :param exit_code: the exit code of the notebook run. 0 for passed test.
        :param experiment: where the test run belong, only necessary when a job is submitted.
        :param namespace: where the pipeline system is deployed.
        """
        self._testname = testname
        self._result = result
        self._exit_code = exit_code
        self._experiment = experiment
        self._namespace = namespace

    def check(self):
        test_cases = []
        test_name = self._testname + ' Sample Test'

        ###### Write the script exit code log ######
        utils.add_junit_test(test_cases, 'test script execution',
                             (self._exit_code == '0'),
                             'test script failure with exit code: '
                             + self._exit_code)

        if self._experiment is not None:  # Bypassing dsl type check sample.
            ###### Initialization ######
            host = 'ml-pipeline.%s.svc.cluster.local:8888' % self._namespace
            client = Client(host=host)

            ###### Get experiments ######
            experiment_id = client.get_experiment(experiment_name=self._experiment).id

            ###### Get runs ######
            list_runs_response = client.list_runs(page_size=_RUN_LIST_PAGE_SIZE,
                                                  experiment_id=experiment_id)

            ###### Check all runs ######
            for run in list_runs_response.runs:
                run_id = run.id
                response = client.wait_for_run_completion(run_id, _TEST_TIMEOUT)
                succ = (response.run.status.lower()=='succeeded')
                utils.add_junit_test(test_cases, 'job completion',
                                     succ, 'waiting for job completion failure')

                ###### Output Argo Log for Debugging ######
                workflow_json = client._get_workflow_json(run_id)
                workflow_id = workflow_json['metadata']['name']
                argo_log, _ = utils.run_bash_command(
                    'argo logs -n {} -w {}'.format(self._namespace, workflow_id))
                print("=========Argo Workflow Log=========")
                print(argo_log)

                if not succ:
                    utils.write_junit_xml(test_name, self._result, test_cases)
                    exit(1)

        ###### Write out the test result in junit xml ######
        utils.write_junit_xml(test_name, self._result, test_cases)