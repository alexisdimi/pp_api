import requests


def get_corpus_zscores(term_uris, cooc_corpus_graph):
    """
    Get zscores for term-term cooccurrences.

    :param term_uris: list: uris of 2 terms
    :param cooc_corpus_graph: graph of corpus coocs
    :return: float [0, 1]: similarity score := zscore/max(zscore)
    """
    def similarity(term1_uri, term2_uri):
        if term1_uri == term2_uri:
            return 1
        elif (term1_uri, term2_uri) in sim_matrix:
            return sim_matrix[(term1_uri, term2_uri)]
        elif (term2_uri, term1_uri) in sim_matrix:
            return sim_matrix[(term2_uri, term1_uri)]
        else:
            return 0

    query_text = """
select ?uri1 ?uri2 ?score where {{
  ?uri1 <http://schema.semantic-web.at/ppcm/2013/5/hasTermCooccurrence> ?co.
  ?co <http://schema.semantic-web.at/ppcm/2013/5/cooccurringExtractedTerm> ?uri2.
  ?co <http://schema.semantic-web.at/ppcm/2013/5/zscore> ?score.
}}"""
    params = {
        'default-graph-uri': '{}'.format(cooc_corpus_graph),
        'query': query_text,
        'format': 'json',
    }
    r = requests.get('https://aligned-virtuoso.poolparty.biz/sparql',
                     auth=('revenkoa', 'revenkpp'),
                     params=params)
    assert r.status_code == 200
    sim_matrix = dict()
    c1 = 0
    c2 = 0
    for binding in r.json()['results']['bindings']:
        uri1 = binding['uri1']['value']
        uri2 = binding['uri2']['value']
        if uri1 in term_uris and uri2 in term_uris:
            sim_matrix[(uri1, uri2)] = np.log2(float(binding['score']['value']))
    max_score = max(sim_matrix.values())
    for k in sim_matrix:
        sim_matrix[k] /= max_score
    return similarity


def get_pp_terms(corpus_graph_terms, CRS_threshold=5):
    """
    Load all terms with combinedRelevanceScore is greater than CRS_threshold
    from the graph corpus_graph_terms.

    :param corpus_graph_terms: uri of the graph
    :param CRS_threshold: min combinedRelevanceScore of term to be returned
    :return:
    """
    params = {
        'default-graph-uri': '{}'.format(corpus_graph_terms),
        'query': """
select ?termUri ?name ?score where {{
  ?termUri <http://schema.semantic-web.at/ppcm/2013/5/combinedRelevanceScore> ?score .
  ?termUri <http://schema.semantic-web.at/ppcm/2013/5/name> ?name .
  filter (?score > {})
}} order by desc(?score)""".format(CRS_threshold),
        'format': 'json',
    }
    r = requests.get('https://aligned-virtuoso.poolparty.biz/sparql',
                     auth=('revenkoa', 'revenkpp'),
                     params=params)
    top_terms_scores = dict()
    top_terms_uris = dict()
    for new_term in r.json()['results']['bindings']:
        name = new_term['name']['value']
        score = float(new_term['score']['value'])
        term_uri = new_term['termUri']['value']
        top_terms_scores[name] = score
        top_terms_uris[name] = term_uri
    return top_terms_scores, top_terms_uris


all_data_q = """
    select distinct * where {{
      ?s ?p ?o
    }}
"""

def query_sparql_endpoint(sparql_endpoint, graph_name, auth_data,
                          query=all_data_q):
    params = {
        'default-graph-uri': '{}'.format(graph_name),
        'query': query,
        'format': 'json',
    }
    r = requests.get(sparql_endpoint, auth=auth_data, params=params)
    if not r.status_code == 200:
        print(r, r.status_code)
        print(r.url)
    assert r.status_code == 200
    return r.json()['results']['bindings']


if __name__ == '__main__':
    pass
