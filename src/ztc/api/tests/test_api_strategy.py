import json
import os
from datetime import timedelta
from unittest import expectedFailure, skip, skipIf

from django.test import LiveServerTestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.settings import api_settings

from oauth2_provider.models import AccessToken, Application

from ...datamodel.models import Catalogus
from .base import APITestCase, CatalogusAPITestMixin, ClientAPITestMixin


class RestfulPrinciplesAPITests(APITestCase):
    """Section 2.6.1 of the DSO: API strategy"""

    def test_nested_resources(self):
        """DSO: API-09 (nested resources)

        An `BesluitType` object can only be part of a `Catalogus` object. Hence, it should be nested under the
        `catalogussen` resource: `/api/v1/catalogussen/1/besluittypen/`.
        """
        kwargs = {
            'version': '1',
            'catalogus_pk': self.catalogus.pk,
            'pk': self.besluittype.pk
        }
        besluittype_list_url = reverse('api:besluittype-detail', kwargs=kwargs)

        self.assertEqual(
            besluittype_list_url,
            '/api/v{version}/catalogussen/{catalogus_pk}/besluittypen/{pk}/'.format(**kwargs)
        )

    def test_expand_all_resources(self):
        """DSO: API-10 (expand all resources)

        Passing `/api/v1/catalogussen/1/?expand=true` expands all (1st level) expandable resources.
        """
        # TODO: Why is this an English term, while search and ordering are Dutch?
        response = self.api_client.get('{}?expand=true'.format(self.detail_url))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # TODO: Extend with other resources.
        expected_expanded_resources = ['besluittypen', ]
        for resource in expected_expanded_resources:
            self.assertGreater(len(data[resource]), 0)
            self.assertIsInstance(data[resource][0], dict)

    def test_expand_single_resource(self):
        """DSO: API-11 (expand single resource)

        Passing `/api/v1/catalogussen/1/?expand=besluittypen` expands only the resource referenced by the field
        "besluittypen".
        """
        response = self.api_client.get('{}?expand=besluittypen'.format(self.detail_url))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        expected_expanded_resource = 'besluittypen'
        self.assertGreater(len(data[expected_expanded_resource]), 0)
        self.assertIsInstance(data[expected_expanded_resource][0], dict)

        # TODO: Extend with other resources.
        expected_closed_resources = []
        for resource in expected_closed_resources:
            self.assertGreater(len(data[resource]), 0)
            self.assertIsInstance(data[resource][0], str)
            self.assertTrue(data[resource][0].startswith('http://'))

    def test_expand_multiple_resources(self):
        """DSO: API-11 (expand multiple resources)

        Passing `/api/v1/catalogussen/1/?expand=besluittypen,informatieobjecttypen` expands only the two resources
        referenced by the field "besluittypen" and "informatieobjecttypen".
        """
        response = self.api_client.get('{}?expand=besluittypen,informatieobjecttypen'.format(self.detail_url))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        # TODO: Extend with other resources.
        expected_expanded_resources = ['besluittypen', ] # 'informatieobjecttypen']
        for resource in expected_expanded_resources:
            self.assertGreater(len(data[resource]), 0)
            self.assertIsInstance(data[resource][0], dict)

        # TODO: Extend with other resources.
        expected_closed_resources = []
        for resource in expected_closed_resources:
            self.assertGreater(len(data[resource]), 0)
            self.assertIsInstance(data[resource][0], str)
            self.assertTrue(data[resource][0].startswith('http://'))

    def test_expand_resource_with_specific_field(self):
        """DSO: API-11 (expand resource with specific field)

        Passing `/api/v1/catalogussen/1/?expand=besluittypen.besluittype_omschrijving` expands only the resource
        referenced by the field "besluittypen" and only shows the field "omschrijving" of that resource.
        """
        response = self.api_client.get('{}?expand=besluittypen.besluittype_omschrijving'.format(self.detail_url))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        expected_expanded_resource = 'besluittypen'
        self.assertGreater(len(data[expected_expanded_resource]), 0)
        self.assertIsInstance(data[expected_expanded_resource][0], dict)
        self.assertEqual(len(data[expected_expanded_resource][0]), 1)
        self.assertTrue('besluittype_omschrijving' in data[expected_expanded_resource][0])

        # TODO: Extend with other resources.
        expected_closed_resources = []
        for resource in expected_closed_resources:
            self.assertGreater(len(data[resource]), 0)
            self.assertIsInstance(data[resource][0], str)
            self.assertTrue(data[resource][0].startswith('http://'))

    def test_specific_single_field(self):
        """DSO: API-12 (specific single field)

        Passing `/api/v1/catalogussen/1/?fields=domein` should only show the resource with the field "domein".
        """
        # TODO: Why is this an English term, while search and ordering are Dutch?
        response = self.api_client.get('{}?fields=domein'.format(self.detail_url))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(len(data), 1)
        self.assertTrue('domein' in data)

    def test_specific_multiple_fields(self):
        """DSO: API-12 (specific multiple fields)

        Passing `/api/v1/catalogussen/1/?fields=domein,rsin` should only show the resource with the 2 fields "domein"
        and "rsin".
        """
        response = self.api_client.get('{}?fields=domein,rsin'.format(self.detail_url))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(len(data), 2)
        self.assertTrue('domein' in data)
        self.assertTrue('rsin' in data)

    @expectedFailure
    def test_specific_unknown_field(self):
        """DSO: API-12 (specific unknown field)

        Passing `/api/v1/catalogussen/1/?fields=foobar` should return a HTTP 400 because the field "foobar" does not
        exist on the catalog resource.
        """
        response = self.api_client.get('{}?fields=foobar'.format(self.detail_url))
        self.assertEqual(response.status_code, 400)


class SecurityAPITests(CatalogusAPITestMixin, LiveServerTestCase):
    """Section 2.6.2 of the DSO: API strategy"""

    def setUp(self):
        super().setUp()

        # Create simple API client that is not authorized.
        self.api_client = self.client_class(content_type='application/json')

    def test_api_key_required(self):
        """DSO: API-15 (API key required)

        A valid API key is required to access any resource.
        """
        response = self.api_client.get(self.list_url)
        self.assertEqual(response.status_code, 401)

    @expectedFailure
    def test_disallow_token_in_query_params(self):
        """DSO: API-16 (disallow token in query params)

        It's not allowed to pass the API key/token via the URL as query parameter.
        """
        # Create a token without the whole authentication flow.
        token = AccessToken.objects.create(
            token='12345', expires=timezone.now() + timedelta(days=1), scope='write read')

        response = self.api_client.get('{}?bearer={}'.format(self.list_url, token.token))
        self.assertEqual(response.status_code, 400)

        response = self.api_client.get('{}?token={}'.format(self.list_url, token.token))
        self.assertEqual(response.status_code, 400)

    def test_oauth2_authentication(self):
        """DSO: API-17 (OAuth2 authentication)

        Test the entire backend application flow:
        https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html#backend-application-flow
        """
        # The `LiveServerTestCase` does not use HTTPS.
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

        # Create application in the ZTC
        application = Application.objects.create(
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS
        )

        # Get token
        from oauthlib.oauth2 import BackendApplicationClient
        from requests_oauthlib import OAuth2Session
        client = BackendApplicationClient(client_id=application.client_id)
        oauth = OAuth2Session(client=client)

        token = oauth.fetch_token(
            token_url='{}/oauth2/token/'.format(self.live_server_url),
            client_id=application.client_id,
            client_secret=application.client_secret
        )

        # We use the live test server rather than the shortcut client.
        list_url = '{}{}'.format(self.live_server_url, self.list_url)

        # Make request using requests_oauthlib
        response = oauth.get(list_url)
        self.assertEqual(response.status_code, 200)

        # Make straightforward request
        response = self.api_client.get(list_url, AUTHORIZATION='Bearer {}'.format(token['access_token']))
        self.assertEqual(response.status_code, 200)

        os.environ.unsetenv('OAUTHLIB_INSECURE_TRANSPORT')


class DocumentationAPITests(ClientAPITestMixin, TransactionTestCase):
    """Section 2.6.3 of the DSO: API strategy"""

    def setUp(self):
        super().setUp()

        self.schema_url = reverse('api:api_schema', kwargs={'version': '1'})

    def test_documentation_is_oas_2(self):
        """DSO: API-19 (documentation is OAS 2)"""
        response = self.api_client.get('{}?format=openapi'.format(self.schema_url))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content.decode('utf-8'))

        self.assertTrue('swagger' in data)
        self.assertEqual(data['swagger'], '2.0')

    def test_documentation_can_be_accepted(self):
        """DSO: API-21 (documentation can be tested)

        This topic is interpreted as the availability of an HTML "document" for the API specification. If you point
        your browser to the schema URL, a nice web page will be shown.
        """
        response = self.client.get(self.schema_url, HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, '<html>')


class VersioningAPITests(APITestCase):
    """Section 2.6.4 of the DSO: API strategy"""

    def test_major_api_version_in_url(self):
        """DSO: API-24 (major API version in URL)"""
        self.assertTrue('/v{}/'.format(api_settings.DEFAULT_VERSION) in self.list_url)

    def test_full_api_version_in_response_header(self):
        """DSO: API-24 (full API version in response header)"""
        response = self.api_client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

        self.assertTrue('API-Version' in response)
        self.assertEqual(response['API-Version'], api_settings.DEFAULT_VERSION)

    @skipIf(api_settings.DEFAULT_VERSION == '1', 'Deprecated API versions should be tested once we get there.')
    def test_deprecated_api_version_warning(self):
        """DSO: API-25 (deprecated API version warning)"""
        pass


class UseJSONTests(APITestCase):
    """Section 2.6.5 of the DSO: API strategy"""

    def test_accept_and_return_json(self):
        """DSO: API-26 (accept and return JSON)"""
        response = self.api_client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response['content-type'], 'application/json')

    @skip('Optional and currently not supported.')
    def test_json_schema_support(self):
        """DSO: API-27 (JSON-schema support)"""
        pass

    @skip('Optional and currently not supported.')
    def test_content_negotiation_xml(self):
        """DSO: API-28 (content negotiation XML)"""
        pass

    def test_content_negotiation_unsupported_format(self):
        """DSO: API-28 (content negotiation unsupported format)"""
        response = self.api_client.get(self.list_url, HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 406)

    @skip('This API is currently read-only.')
    def test_content_type_header_is_required(self):
        """DSO: API-29 (content type header is required)

        Typically, this header is passed on POST/PUT/PATCH requests to indicate the body content type.
        """
        response = self.api_client.put(self.detail_url, '{}', content_type='text/html')
        self.assertEqual(response.status_code, 415)

    @expectedFailure
    def test_camelcase_field_names(self):
        """DSO: API-30 (camelCase field names)"""
        # TODO: We deviate from this guideline and use snake case.
        response = self.api_client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('contactpersoonBeheerNaam' in data)

    def test_no_pretty_print(self):
        """DSO: API-31 (no pretty print)"""
        response = self.api_client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)

        raw_data = response.content.decode('utf-8')

        self.assertFalse(' ' in raw_data)
        self.assertFalse('\n' in raw_data)

    def test_no_envelope(self):
        """DSO: API-32 (no envelope)"""
        # TODO: List resources do have envelopes, even suggested by DSO.
        response = self.api_client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('contactpersoon_beheer_naam' in data)

    @skip('This API is currently read-only.')
    def test_content_type_json_is_supported(self):
        """DSO: API-33 (content type application/json is supported)"""
        response = self.api_client.patch(self.detail_url, '{}')
        self.assertEqual(response.status_code, 200)

        response = self.api_client.put(self.detail_url, '{}')
        self.assertEqual(response.status_code, 200)

        response = self.api_client.post(self.list_url, '{}')
        self.assertEqual(response.status_code, 201)

    @skip('This API is currently read-only.')
    def test_content_type_x_is_not_supported(self):
        """DSO: API-33 (content type application/x-www-form-urlencoded is not supported)"""
        # TODO: This guideline contradicts OAuth2 standards...
        response = self.api_client.patch(self.detail_url, '{}', content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 415)

        response = self.api_client.put(self.detail_url, '{}', content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 415)

        response = self.api_client.post(self.list_url, '{}', content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 415)


class FilterSortSearchTests(APITestCase):
    """Section 2.6.6 of the DSO: API strategy"""
    def setUp(self):
        super().setUp()

        self.other_catalogus = Catalogus.objects.create(
            domein=self.catalogus.domein, rsin='999999999', contactpersoon_beheer_naam='John Doe')

    def test_filter_on_single_field(self):
        """DSO: API-34 (filter on single field)"""
        # Filter on rsin
        response = self.api_client.get('{}?rsin={}'.format(self.list_url, self.catalogus.rsin))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['rsin'], self.catalogus.rsin)

        # Filter on domain
        response = self.api_client.get('{}?domein={}'.format(self.list_url, self.catalogus.domein))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 2)

    def test_filter_on_multiple_fields(self):
        """DSO: API-34 (filter on multiple fields)"""

        # Create an extra catalog to make sure it gets filtered out because of the different domain.
        Catalogus.objects.create(domein='XXXXX', rsin=self.catalogus.rsin)

        response = self.api_client.get('{}?rsin={}&domein={}'.format(self.list_url, self.catalogus.rsin, self.catalogus.domein))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['rsin'], self.catalogus.rsin)

    def test_sort_query_param_is_called_sorteer(self):
        """DSO: API-35 (sort query param is called sorteer)"""
        # TODO: But why? expand is English...
        self.assertEqual(api_settings.ORDERING_PARAM, 'sorteer')

    def test_sort_ascending(self):
        """DSO: API-35 (sort ascending)"""
        response = self.api_client.get('{}?sorteer=rsin'.format(self.list_url))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['results'][0]['rsin'], self.catalogus.rsin)
        self.assertEqual(data['results'][1]['rsin'], self.other_catalogus.rsin)

    def test_sort_descending(self):
        """DSO: API-35 (sort descending)"""
        response = self.api_client.get('{}?sorteer=-rsin'.format(self.list_url))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['results'][0]['rsin'], self.other_catalogus.rsin)
        self.assertEqual(data['results'][1]['rsin'], self.catalogus.rsin)

    def test_search_query_param_is_called_zoek(self):
        """DSO: API-36 (search query param is called zoek)"""
        # TODO: But why? expand is English...
        self.assertEqual(api_settings.SEARCH_PARAM, 'zoek')

    def test_search_single_value(self):
        """DSO: API-36 (search single value)"""
        response = self.api_client.get('{}?zoek={}'.format(self.list_url, self.catalogus.rsin))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['rsin'], self.catalogus.rsin)

    def test_search_partial_value(self):
        """DSO: API-36 (search partial value)"""
        # TODO: This should probably not work but should only work when using wildcards.

        response = self.api_client.get('{}?zoek={}'.format(self.list_url, 'Jo'))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['rsin'], self.other_catalogus.rsin)

    def test_search_multiple_values(self):
        """DSO: API-36 (search multiple values)"""
        response = self.api_client.get('{}?zoek={} {}'.format(self.list_url, 'John', self.other_catalogus.rsin))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['rsin'], self.other_catalogus.rsin)

        # Another test to check whether it searching multiple values matches ALL search terms, and not just one.
        response = self.api_client.get('{}?zoek={} {}'.format(self.list_url, 'Jane', self.other_catalogus.rsin))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 0)


    def test_search_filter_and_sorting_combined(self):
        """Combination of DSO: API-34, API-35, API-36"""

        # There will be 4 catalogs now.
        catalogus_3 = Catalogus.objects.create(
            domein=self.catalogus.domein, rsin='111111111', contactpersoon_beheer_naam='Jane Doe')
        catalogus_4 = Catalogus.objects.create(
            domein=self.catalogus.domein, rsin='222222222', contactpersoon_beheer_naam='Jane Doe')

        # All query parameters will filter it down to 2, that are ordered.
        response = self.api_client.get('{}?domein={}&zoek={}&sorteer={}'.format(
            self.list_url, self.catalogus.domein, 'Jane', 'rsin'))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['results'][0]['rsin'], catalogus_3.rsin)
        self.assertEqual(data['results'][1]['rsin'], catalogus_4.rsin)

    @expectedFailure
    def test_search_wildcard_star(self):
        """DSO: API-37 (search wildcard star)"""
        response = self.api_client.get('{}?zoek={}*'.format(self.list_url, self.other_catalogus.rsin[0:4]))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 1)

    @expectedFailure
    def test_search_wildcard_question_mark(self):
        """DSO: API-37 (search wildcard question mark)"""
        response = self.api_client.get('{}?zoek={}??????'.format(self.list_url, self.other_catalogus.rsin[0:4]))
        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue('results' in data)
        self.assertEqual(len(data['results']), 1)
