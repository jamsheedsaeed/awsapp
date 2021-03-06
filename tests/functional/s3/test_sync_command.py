# Copyright 2013 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
import os

from awscli.compat import six
from awscli.testutils import set_invalid_utime, mock
from tests.functional.s3 import BaseS3TransferCommandTest


class TestSyncCommand(BaseS3TransferCommandTest):

    prefix = 's3 sync '

    def test_website_redirect_ignore_paramfile(self):
        full_path = self.files.create_file('foo.txt', 'mycontent')
        cmdline = '%s %s s3://bucket/key.txt --website-redirect %s' % \
            (self.prefix, self.files.rootdir, 'http://someserver')
        self.parsed_responses = [
            {"CommonPrefixes": [], "Contents": []},
            {'ETag': '"c8afdb36c52cf4727836669019e69222"'}
        ]
        self.run_cmd(cmdline, expected_rc=0)

        # The only operations we should have called are ListObjectsV2/PutObject.
        self.assertEqual(len(self.operations_called), 2, self.operations_called)
        self.assertEqual(self.operations_called[0][0].name, 'ListObjectsV2')
        self.assertEqual(self.operations_called[1][0].name, 'PutObject')
        # Make sure that the specified web address is used as opposed to the
        # contents of the web address when uploading the object
        self.assertEqual(
            self.operations_called[1][1]['WebsiteRedirectLocation'],
            'http://someserver'
        )

    def test_no_recursive_option(self):
        cmdline = '. s3://mybucket --recursive'
        # Return code will be 252 for invalid parameter ``--recursive``
        self.run_cmd(cmdline, expected_rc=252)

    def test_sync_from_non_existant_directory(self):
        non_existant_directory = os.path.join(self.files.rootdir, 'fakedir')
        cmdline = '%s %s s3://bucket/' % (self.prefix, non_existant_directory)
        self.parsed_responses = [
            {"CommonPrefixes": [], "Contents": []}
        ]
        _, stderr, _ = self.run_cmd(cmdline, expected_rc=255)
        self.assertIn('does not exist', stderr)

    def test_sync_to_non_existant_directory(self):
        key = 'foo.txt'
        non_existant_directory = os.path.join(self.files.rootdir, 'fakedir')
        cmdline = '%s s3://bucket/ %s' % (self.prefix, non_existant_directory)
        self.parsed_responses = [
            {"CommonPrefixes": [], "Contents": [
                {"Key": key, "Size": 3,
                 "LastModified": "2014-01-09T20:45:49.000Z"}]},
            {'ETag': '"c8afdb36c52cf4727836669019e69222-"',
             'Body': six.BytesIO(b'foo')}
        ]
        self.run_cmd(cmdline, expected_rc=0)
        # Make sure the file now exists.
        self.assertTrue(
            os.path.exists(os.path.join(non_existant_directory, key)))

    def test_glacier_sync_with_force_glacier(self):
        self.parsed_responses = [
            {
                'Contents': [
                    {'Key': 'foo/bar.txt', 'ContentLength': '100',
                     'LastModified': '00:00:00Z',
                     'StorageClass': 'GLACIER',
                     'Size': 100},
                ],
                'CommonPrefixes': []
            },
            {'ETag': '"foo-1"', 'Body': six.BytesIO(b'foo')},
        ]
        cmdline = '%s s3://bucket/foo %s --force-glacier-transfer' % (
            self.prefix, self.files.rootdir)
        self.run_cmd(cmdline, expected_rc=0)
        self.assertEqual(len(self.operations_called), 2, self.operations_called)
        self.assertEqual(self.operations_called[0][0].name, 'ListObjectsV2')
        self.assertEqual(self.operations_called[1][0].name, 'GetObject')

    def test_handles_glacier_incompatible_operations(self):
        self.parsed_responses = [
            {'Contents': [
                {'Key': 'foo', 'Size': 100,
                 'LastModified': '00:00:00Z', 'StorageClass': 'GLACIER'},
                {'Key': 'bar', 'Size': 100,
                 'LastModified': '00:00:00Z', 'StorageClass': 'DEEP_ARCHIVE'}
            ]}
        ]
        cmdline = '%s s3://bucket/ %s' % (
            self.prefix, self.files.rootdir)
        _, stderr, _ = self.run_cmd(cmdline, expected_rc=2)
        # There should not have been a download attempted because the
        # operation was skipped because it is glacier and glacier
        # deep archive incompatible.
        self.assertEqual(len(self.operations_called), 1)
        self.assertEqual(self.operations_called[0][0].name, 'ListObjectsV2')
        self.assertIn('GLACIER', stderr)
        self.assertIn('s3://bucket/foo', stderr)
        self.assertIn('s3://bucket/bar', stderr)

    def test_turn_off_glacier_warnings(self):
        self.parsed_responses = [
            {'Contents': [
                {'Key': 'foo', 'Size': 100,
                 'LastModified': '00:00:00Z', 'StorageClass': 'GLACIER'},
                {'Key': 'bar', 'Size': 100,
                 'LastModified': '00:00:00Z', 'StorageClass': 'DEEP_ARCHIVE'}
            ]}
        ]
        cmdline = '%s s3://bucket/ %s --ignore-glacier-warnings' % (
            self.prefix, self.files.rootdir)
        _, stderr, _ = self.run_cmd(cmdline, expected_rc=0)
        # There should not have been a download attempted because the
        # operation was skipped because it is glacier incompatible.
        self.assertEqual(len(self.operations_called), 1)
        self.assertEqual(self.operations_called[0][0].name, 'ListObjectsV2')
        self.assertEqual('', stderr)

    def test_warning_on_invalid_timestamp(self):
        full_path = self.files.create_file('foo.txt', 'mycontent')

        # Set the update time to a value that will raise a ValueError when
        # converting to datetime
        set_invalid_utime(full_path)
        cmdline = '%s %s s3://bucket/key.txt' % \
                  (self.prefix, self.files.rootdir)
        self.parsed_responses = [
            {"CommonPrefixes": [], "Contents": []},
            {'ETag': '"c8afdb36c52cf4727836669019e69222"'}
        ]
        self.run_cmd(cmdline, expected_rc=2)

        # We should still have put the object
        self.assertEqual(len(self.operations_called), 2, self.operations_called)
        self.assertEqual(self.operations_called[0][0].name, 'ListObjectsV2')
        self.assertEqual(self.operations_called[1][0].name, 'PutObject')

    def test_sync_with_delete_on_downloads(self):
        full_path = self.files.create_file('foo.txt', 'mycontent')
        cmdline = '%s s3://bucket %s --delete' % (
            self.prefix, self.files.rootdir)
        self.parsed_responses = [
            {"CommonPrefixes": [], "Contents": []},
            {'ETag': '"c8afdb36c52cf4727836669019e69222"'}
        ]
        self.run_cmd(cmdline, expected_rc=0)

        # The only operations we should have called are ListObjectsV2.
        self.assertEqual(len(self.operations_called), 1, self.operations_called)
        self.assertEqual(self.operations_called[0][0].name, 'ListObjectsV2')

        self.assertFalse(os.path.exists(full_path))

    # When a file has been deleted after listing,
    # awscli.customizations.s3.utils.get_file_stat may raise either some kind
    # of OSError, or a ValueError, depending on the environment. In both cases,
    # the behaviour should be the same: skip the file and emit a warning.
    #
    # This test covers the case where a ValueError is emitted.
    def test_sync_skips_over_files_deleted_between_listing_and_transfer_valueerror(self):
        full_path = self.files.create_file('foo.txt', 'mycontent')
        cmdline = '%s %s s3://bucket/' % (
            self.prefix, self.files.rootdir)

        # FileGenerator.list_files should skip over files that cause an
        # IOError to be raised because they are missing when we try to
        # get their stats. This IOError is translated to a ValueError in
        # awscli.customizations.s3.utils.get_file_stat.
        def side_effect(_):
            os.remove(full_path)
            raise ValueError()
        with mock.patch(
                'awscli.customizations.s3.filegenerator.get_file_stat',
                side_effect=side_effect
                ):
            self.run_cmd(cmdline, expected_rc=2)

        # We should not call PutObject because the file was deleted
        # before we could transfer it
        self.assertEqual(len(self.operations_called), 1, self.operations_called)
        self.assertEqual(self.operations_called[0][0].name, 'ListObjectsV2')

    # This test covers the case where an OSError is emitted.
    def test_sync_skips_over_files_deleted_between_listing_and_transfer_oserror(self):
        full_path = self.files.create_file('foo.txt', 'mycontent')
        cmdline = '%s %s s3://bucket/' % (
            self.prefix, self.files.rootdir)

        # FileGenerator.list_files should skip over files that cause an
        # OSError to be raised because they are missing when we try to
        # get their stats.
        def side_effect(_):
            os.remove(full_path)
            raise OSError()
        with mock.patch(
                'awscli.customizations.s3.filegenerator.get_file_stat',
                side_effect=side_effect
                ):
            self.run_cmd(cmdline, expected_rc=2)

        # We should not call PutObject because the file was deleted
        # before we could transfer it
        self.assertEqual(len(self.operations_called), 1, self.operations_called)
        self.assertEqual(self.operations_called[0][0].name, 'ListObjectsV2')

    def test_request_payer(self):
        cmdline = '%s s3://sourcebucket/ s3://mybucket --request-payer' % (
            self.prefix)
        self.parsed_responses = [
            # Response for ListObjects on source bucket
            self.list_objects_response(['mykey']),
            # Response for ListObjects on destination bucket
            self.list_objects_response([]),
            self.copy_object_response(),
        ]
        self.run_cmd(cmdline, expected_rc=0)
        self.assert_operations_called(
            [
                self.list_objects_request(
                    'sourcebucket', RequestPayer='requester'),
                self.list_objects_request(
                    'mybucket', RequestPayer='requester'),
                self.copy_object_request(
                    'sourcebucket', 'mykey', 'mybucket', 'mykey',
                    RequestPayer='requester')
            ]
        )

    def test_request_payer_with_deletes(self):
        cmdline = '%s s3://sourcebucket/ s3://mybucket' % self.prefix
        cmdline += ' --request-payer'
        cmdline += ' --delete'
        self.parsed_responses = [
            # Response for ListObjects on source bucket
            self.list_objects_response([]),
            # Response for ListObjects on destination bucket
            self.list_objects_response(['key-to-delete']),
            self.delete_object_response()
        ]
        self.run_cmd(cmdline, expected_rc=0)
        self.assert_operations_called(
            [
                self.list_objects_request(
                    'sourcebucket', RequestPayer='requester'),
                self.list_objects_request(
                    'mybucket', RequestPayer='requester'),
                self.delete_object_request(
                    'mybucket', 'key-to-delete', RequestPayer='requester'),
            ]
        )

    def test_with_accesspoint_arn(self):
        accesspoint_arn = (
            'arn:aws:s3:us-west-2:123456789012:accesspoint/endpoint'
        )
        cmdline = self.prefix
        cmdline += 's3://%s' % accesspoint_arn
        cmdline += ' %s' % self.files.rootdir
        self.parsed_responses = [
            self.list_objects_response(['mykey']),
            self.get_object_response(),
        ]
        self.run_cmd(cmdline, expected_rc=0)
        self.assert_operations_called(
            [
                self.list_objects_request(accesspoint_arn),
                self.get_object_request(accesspoint_arn, 'mykey')
            ]
        )

    def test_with_copy_props(self):
        cmdline = self.prefix
        cmdline += 's3://sourcebucket/ s3://bucket/'
        cmdline += ' --copy-props default'

        upload_id = 'upload_id'
        large_tag_set = {'tag-key': 'val' * 3000}
        metadata = {'tag-key': 'tag-value'}
        self.parsed_responses = [
            self.list_objects_response(keys=['key'], Size=8 * 1024 ** 2),
            self.list_objects_response(keys=[]),
            self.head_object_response(
                Metadata=metadata,
            ),
            self.get_object_tagging_response(large_tag_set),
            self.create_mpu_response(upload_id),
            self.upload_part_copy_response(),
            self.complete_mpu_response(),
            self.put_object_tagging_response(),
        ]
        self.run_cmd(cmdline, expected_rc=0)
        self.assert_operations_called(
            [
                self.list_objects_request('sourcebucket'),
                self.list_objects_request('bucket'),
                self.head_object_request('sourcebucket', 'key'),
                self.get_object_tagging_request('sourcebucket', 'key'),
                self.create_mpu_request('bucket', 'key', Metadata=metadata),
                self.upload_part_copy_request(
                    'sourcebucket', 'key', 'bucket', 'key', upload_id,
                    CopySourceRange=mock.ANY, PartNumber=1,
                ),
                self.complete_mpu_request('bucket', 'key', upload_id, 1),
                self.put_object_tagging_request(
                    'bucket', 'key', large_tag_set
                ),
            ]
        )
