from requests.exceptions import HTTPError

from pp_api import utils as u
from pp_api import pp_calls


class GraphSearch:
    def __init__(self, server, auth_data=None, session=None):
        self.server = server
        session = u.get_session(session, auth_data)
        self.auth_data = auth_data
        self.session = session

    def delete(self, search_space_id, id_=None, source=None):
        if id_ is not None:
            suffix = '/GraphSearch/api/content/delete/id'
            data = {
                'identifier': id_,
                'searchSpaceId': search_space_id
            }
        elif source is not None:
            suffix = '/GraphSearch/api/content/delete/source'
            data = {
                'identifier': source,
            }
        else:
            assert 0
        r = self.session.post(
            self.server + suffix,
            json=data,
        )
        r.raise_for_status()
        return r

    def clean(self, search_space_id):
        """
        Remove first 100000 document from GraphSearch.
        """
        r = self.search(
            count=100000,
            search_space_id=search_space_id
        )
        for result in r.json()['results']:
            id_ = result['id']
            r = self.delete(
                id_=id_,
                search_space_id=search_space_id
            )
        return r.json()['results']

    def in_gs(self, uri, search_space_id):
        """
        Check if document with specified uri is contained in GS

        :param uri: document uri
        :return: Boolean
        """
        id_filter = self.filter_id(id_=uri)
        r = self.search(search_space_id=search_space_id,
                        search_filters=id_filter)
        return r.json()['total'] > 0

    def _create(self, id_, title, author, date, search_space_id,
                text=None, update=False,
                text_limit=True, **kwargs):
        """

        :param id_: should be a URL starting from protocol (e.g. http://)
        :param title:
        :param author:
        :param date: datetime object
        :param kwargs: any additional fields in key=value format. Fields should exist in GS.
        :return:
        """
        if text_limit and len(text) > 12048:
            text = text[:12000]
        if not update:
            suffix = '/GraphSearch/api/content/create'
        else:
            suffix = '/GraphSearch/api/content/update'
        data = {
            'identifier': id_,
            'title': title,
            'author': author,
            'date': date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'text': text,
            'useExtraction': False,
            'searchSpaceId': search_space_id
        }
        for k, v in kwargs.items():
            if k is not None and v is not None:
                data[k] = v
        r = self.session.post(
            self.server + suffix,
            json=data,
        )
        try:
            r.raise_for_status()
        except HTTPError as e:
            print(r.text)
            raise e
        return r

    def create_with_freqs(self, id_, title, author, date, cpts, search_space_id,
                          image_url=None,
                          text=None, update=False):
        cpt_uris = [x['uri'] for x in cpts]
        cpt_freqs = {
            x['uri'].split("/")[-1]: x['frequencyInDocument'] for x in cpts
        }
        cpt_facets = {
            ('dyn_flt_' + suffix): [freq] for suffix, freq in cpt_freqs.items()
        }
        cpt_facets.update({
            'dyn_uri_all_concepts': cpt_uris
        })
        return self._create(
            id_=id_, title=title, author=author, date=date,
            text=text, facets=cpt_facets,
            update=update, search_space_id=search_space_id,
            dyn_txt_image=image_url
        )

    def extract_and_create(self, pid, id_, title, author, date, text,
                           search_space_id,
                           image_url=None,
                           text_to_extract=None,
                           update=False,
                           lang='en'):
        """
        Extract concepts from the text and create corresponding document with
        concept frequencies.

        :param pid: project id of the thesaurus in PoolParty
        :param id_:
        :param title:
        :param author:
        :param date:
        :param text:
        :return:
        """
        pp = pp_calls.PoolParty(server=self.server, auth_data=self.auth_data)
        if text_to_extract is None:
            text_to_extract = text
        r = pp.extract(
            pid=pid, text=text_to_extract, lang=lang
        )
        cpts = pp_calls.get_cpts_from_response(r)
        self.create_with_freqs(
            id_=id_, title=title, author=author,
            date=date, text=text, cpts=cpts, update=update,
            search_space_id=search_space_id, image_url=image_url
        )
        return cpts

    def extract_and_update(self, *args, **kwargs):
        return self.extract_and_create(*args, update=True, **kwargs)

    def search(self, search_space_id, search_filters=None, locale='en',
               **kwargs):
        """

        :param search_space_id: ID of search space from GS admin->configuration
        :param search_filters: the filters (usually prepared by other methods of GS
        :param locale: language (default: 'en')
        :param kwargs: other kwargs, for example,
            count - total number of results,
            start - start index
        :return: results as returned by GS API call
        """
        suffix = '/GraphSearch/api/search'
        data = {
            'searchSpaceId': search_space_id,
            'locale': locale,
            'documentFacets': ['all']
        }
        if search_filters is not None:
            data.update({'searchFilters': search_filters})
        if kwargs:
            data.update(**kwargs)
        r = self.session.post(
            self.server + suffix,
            json=data,
        )
        try:
            r.raise_for_status()
        except HTTPError as e:
            print(r.request.__dict__)
            print(r.text)
            raise e
        return r

    @staticmethod
    def filter_full_text(query_str):
        search_filters = [
            {'field': 'full_text_search',
             'value': query_str,
             'optional': False}
        ]
        return search_filters

    @staticmethod
    def filter_cpt(cpt_uri):
        search_filters = [
            {'field': 'dyn_uri_all_concepts',
             'value': cpt_uri}
        ]
        return search_filters

    @staticmethod
    def filter_author(author):
        search_filters = [
            {'field': 'dyn_lit_author',
             'value': author}
        ]
        return search_filters

    @staticmethod
    def filter_id(id_):
        search_filters = [
            {'field': 'identifier',
             'value': id_}
        ]
        return search_filters

    @staticmethod
    def filter_date(start_date=None, finish_date=None):
        """

        :param start: datetime object
        :param finish: datetime object
        :return:
        """
        start_str = (start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                     if start_date
                     else "1970-01-01T23:00:00.000Z")
        finish_str = (finish_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                      if finish_date
                      else "NOW")
        date_str = '[{start} TO {finish}]'.format(start=start_str, finish=finish_str)
        search_filters = [
            {'field': 'date',
             'value': date_str}
        ]
        return search_filters

    def get_fields(self):
        suffix = '/GraphSearch/admin/config/fields'
        r = self.session.get(
            self.server + suffix,
        )
        try:
            r.raise_for_status()
        except HTTPError as e:
            print(r.request.__dict__)
            print(r.text)
            raise e
        return r

    def add_field(self, space_id, field, label):
        suffix = '/GraphSearch/admin/suggest/add'
        data = {
            'searchSpaceId': space_id,
            'field': field,
            'label': label
        }
        r = self.session.post(
            self.server + suffix,
            params=data,
            # data=data
        )
        try:
            r.raise_for_status()
        except HTTPError as e:
            print(r.request.__dict__)
            print(r.text)
            raise e
        return r

    def remove_field(self, space_id, field):
        suffix = '/GraphSearch/admin/suggest/delete'
        data = {
            'searchSpaceId': space_id,
            'field': field
        }
        r = self.session.post(
            self.server + suffix,
            params=data,
            # data=data
        )
        try:
            r.raise_for_status()
        except HTTPError as e:
            print(r.request.__dict__)
            print(r.text)
            raise e
        return r


def sort_by_date(gs_results):
    ans = sorted(
        gs_results,
        key=lambda x: x['date']
    )
    return ans


def add_custom_fields_from_the(search_space_id, pid, pp, gs, the_path):
    # TODO: debug
    from thesaurus.thesaurus import Thesaurus

    the = Thesaurus.get_the_pp(
        the_path=the_path, pp=pp, pid=pid
    )
    all_cpts = the.get_all_concepts_and_pref_labels(lang='en')
    fields = [x['field'] for x in gs.get_fields().json()['searchFields']]
    for uri, pl in all_cpts.items():
        field_str = "dyn_flt_" + uri.split("/")[-1]
        if field_str in fields:
            continue
        else:
            r = gs.add_field(
                space_id=search_space_id,
                field=field_str,
                label=pl
            )


if __name__ == '__main__':
    pass
