import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from rdflib import Graph, URIRef
from rdflib.namespace import NamespaceManager
from typing import Dict
# from pprint import pprint
from datetime import datetime
from ontology2smw.jinja_utils import url_termination, render_template
from ontology2smw.mediawikitools import actions as mwactions
from ontology2smw.file_utils import relative_read_f, write2file

all_ns_dict = relative_read_f('queries/all_ns_prefixes.json', format_='json')

xsd2smwdatatype = {
    'xsd:string': 'Text',
    'rdfs:Literal': 'Text',
    'xsd:Name': 'Text',
    'xsd:normalizedString': 'Text',
    'xsd:decimal': 'Number',
    'xsd:float': 'Number',
    'xsd:integer': 'Number',
    'xsd:nonNegativeInteger': 'Number',
    'xsd:positiveInteger': 'Number',
    'xsd:nonPositiveInteger': 'Number',
    'xsd:negativeInteger': 'Number',
    'xsd:int': 'Number',
    'xsd:double': 'Number',
    'xsd:long': 'Number',
    'xsd:short': 'Number',
    'xsd:unsignedLong': 'Number',
    'xsd:byte': 'Number',
    'xsd:boolean': 'Boolean',
    'xsd:dateTime': 'Date',
    'xsd:time': 'Text',
    'xsd:date': 'Date',
    'xsd:gYearMonth': 'Date',
    'xsd:gYear': 'Date',
    'xsd:gMonthDay': 'Text',
    'xsd:gDay': 'Text',
    'xsd:gMonth': 'Text',
    'xsd:anyURI': 'URL',
    'xsd:language': 'Text'
}


def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


class MWpage:
    """
    Parent Class represents MW page:
    """
    def __init__(self):
        self.wikipage_name = None
        self.wikipage_content = None

    def write_wikipage(self):
        now = datetime.now().isoformat()
        edit_response = mwactions.edit(page=self.wikipage_name,
                                       content=self.wikipage_content,
                                       summary=f'Edited by Bot at {now}',
                                       append=False,
                                       newpageonly=False)
        if edit_response:
            print(f'Wrote {self.wikipage_name} to wiki')
        else:
            print(f'Failed to write {self.wikipage_name} to wiki')


class QueryOntology:
    """
    SPARQL query to Ontology Schema
    """
    def __init__(self, sparql_fn: str, source: str,
                 format_: str):
        self.sparql_fn = sparql_fn
        self.format = format_  # TODO: rm format and infer from source=*.ext
        self.source = source
        self.graph = Graph()
        self.bind_namespaces()
        self.graph.parse(source=self.source, format=self.format)
        self.printouts = None
        self.prefixes = None
        self.query = None  # TMP

    def bind_namespaces(self):
        for prefix, ns in all_ns_dict.items():
            self.graph.bind(prefix, ns)

    def get_graph_prefixes(self):
        namespace_manager = NamespaceManager(self.graph)
        all_prefixes = {n[0]: n[1] for n in namespace_manager.namespaces()}
        # all_prefixes.pop('')  # remove '' key
        self.prefixes = all_prefixes

    def query_graph(self):
        with open(self.sparql_fn, 'r') as query_fobj:
            self.query = query_fobj.read()  # TMP
            sparq_query = self.query  # query_fobj.read()
        self.printouts = self.graph.query(sparq_query)
        # TODO: handle errors

    def return_printout(self):
        self.query_graph()
        for printout_ in self.printouts:
            yield printout_


class SMWCategoryORProp(MWpage):
    """
    Class represents a SMW Category or Property
    """
    def __init__(self, item_: Dict, query_):
        self.term_dict = item_.asdict()
        self.term = self.term_dict['term']  # used inside
        self.term_name = url_termination(self.term)  # used outside
        self.query = query_
        self.namespace, self.namespace_prefix = self.get_term_ns_prefix()
        # self.namespace_prefix  used outside
        self.query_nsmanager = self.query.graph.namespace_manager
        self.resource_type = self.determine_smw_catORprop()  # used outside
        if self.resource_type == 'Property':
            self.prop_datatype = self.determine_smw_prop_datatype()
        else:
            self.prop_datatype = None
        self.create_wiki_item()

    def get_term_ns_prefix(self):
        """
        Determine the prefix of term
        """
        # if self.term == https... -> http_or_https_term == http...
        # so both can be search in loop below
        if self.term.startswith('https'):
            http_or_https_term = self.term.replace('https', 'http')
        else:
            http_or_https_term = self.term.replace('http', 'https')
        # loop through prefixes:namespace dict of self.query.prefixes
        # self.query.prefixes were bound from all_ns_prefixes.json in
        # class QueryOntology self.bind_namespaces() method
        # print(self.term)
        for prefix, namespace in self.query.prefixes.items():
            if (namespace in self.term or namespace in http_or_https_term)\
                    and prefix:
                # prefixes can have an appended number if there is more than
                # 1 prefix w
                # same name in self.query.prefixes
                # hence remove that last number
                if prefix[-1].isnumeric():
                    prefix = prefix[:-1]
                return namespace, prefix
        # when prefix cannot be found in self.query.prefixes
        # promp user to provide the prefix for the NS
        # and update self.query.prefixes
        namespace = self.term.replace(self.term_name, '')
        prefix = input(f"\n\nThe prefix to Namespace {namespace} CANNOT be "
                       f"found.\nPlease provide it: ")
        self.query.prefixes[prefix] = URIRef(namespace)

        return namespace, prefix

    def create_wiki_item(self):
        self.wikipage_name = f'{self.resource_type.capitalize()}:' \
                             f'{self.term_name}'
        self.wikipage_content = None

        if self.resource_type.lower() == 'category':
            template_file = 'mw_category.j2'
        else:
            template_file = 'mw_property.j2'
        self.wikipage_content = render_template(
            template=template_file,
            ns_prefix=self.namespace_prefix,
            term_dict=self.term_dict,
            term_name=self.term_name,
            page_info=None,
            prop_datatype=self.prop_datatype
        )

    def determine_smw_catORprop(self):
        if 'smw_datatype' in self.term_dict.keys():
            if str(self.term_dict['smw_datatype']) == 'Category':
                return 'Category'
            else:
                return 'Property'
        else:
            termtype = url_termination(self.term_dict.get('termType')
                                       ).capitalize()
            if termtype == 'Class':
                return 'Category'
            else:
                return 'Property'

    def determine_smw_prop_datatype(self):
        # rdfs:type DatatypeProprety terms are queried for their range
        # ObjectTypeProperty terms have entities as range, hence:
        # ObjectTypeProperty range == SMW Has type::Page
        # DatatypeProprety items: match rdf:range value to xsd2smwdatatype
        if self.term_dict.get('range'):  # certainly a DatatypeProprety
            # get range with prefix
            range_ = self.term_dict.get('range').n3(self.query_nsmanager)
            if range_ in xsd2smwdatatype.keys():
                # if there is a range value search in xsd2smwdatatype
                return xsd2smwdatatype[range_]
            else:  # if the range values is not found in xsd2smwdatatype
                return 'Text'
        else:
            # defaults
            if 'DatatypeProperty' in self.term_dict.get('termType'):
                return 'Text'
            elif 'ObjectProperty' in self.term_dict.get('termType'):
                return 'Page'


class SMWImportOverview(MWpage):
    """
    Class represents the Ontology overview SMW page: Mediawiki:smw_import_XYZ
    """
    def __init__(self, ontology_ns: str, ontology_ns_prefix: str,
                 ontology_format: str):
        self.ontology_ns = ontology_ns
        self.ontology_ns_prefix = ontology_ns_prefix
        self.ontology_format = ontology_format
        self.terms = []
        self.ontology_name = None
        self.wikipage_name = f'Mediawiki:Smw_import_{self.ontology_ns_prefix}'
        self.title, self.version, self.desc = self.get_ontology_details()

    def create_smw_import(self):
        page_info_dict = {'ontology_ns': self.ontology_ns,
                          'ontology_ns_prefix': self.ontology_ns_prefix,
                          'ontology_name': self.ontology_name,
                          }
        self.wikipage_content = render_template(
            template='mw_smw_import.j2',
            ns_prefix=self.ontology_ns_prefix,
            term_dict=self.terms,  # self.terms isn't a dict but [(term,type)]
            term_name=None,
            page_info=page_info_dict,
        )

    def can_resolve_uri(self, uri, contenttype):
        try:
            response = requests_retry_session().get(
                url=uri,
                headers={'Accept': contenttype},
                timeout=0.2)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            return False
        except requests.exceptions.ConnectTimeout:
            return False
        except requests.exceptions.Timeout:
            return False
        except requests.exceptions.ConnectionError:
            return False
        else:
            if response.headers.get('content-type') == contenttype:
                # dismiss the cases where html is returned
                return True
            else:
                return False

    def get_ontology_details(self):
        """
        Tries to find ontology title, verion, description
        default value title = self.ontology_ns_prefix
        """
        title, version, description = self.ontology_ns_prefix, None, None
        can_resolve = self.can_resolve_uri(
            uri=self.ontology_ns,
            contenttype="application/rdf+xml"
        )
        if can_resolve:
            graph = Graph()
            # print(self.ontology_ns, self.ontology_format)
            graph.parse(location=self.ontology_ns,
                        format="application/rdf+xml")
            sparql_query = relative_read_f('queries/query_ontology_schema.rq')
            # print(sparql_query)
            printouts = graph.query(sparql_query)
            if len(printouts) > 0:
                printout_dict = (list(printouts)[0]).asdict()
                if printout_dict.get('title'):
                    title = printout_dict.get('title')
                version = printout_dict.get('version')
                description = printout_dict.get('description')

        return title, version, description


class Report():
    def __init__(self, importdict, cli_arg_write, verbose, output, cache):
        self.importdict = importdict
        self.cli_arg_write = cli_arg_write
        self.verbose = verbose
        self.output_file = output
        self.report_cache = cache
        self.report = self.create_report()

    def create_report(self):
        report = '\n*********** Import Report: ***********\n'
        for smwimportoverview in self.importdict.values():
            prefix = smwimportoverview.ontology_ns_prefix
            # todo: prepend wiki url if --write
            wikipage_name = smwimportoverview.wikipage_name
            if self.verbose is True:
                wikipage_str = f'\n{"-" * 15}\n{wikipage_name}\n{"-" * 15}\n'
                self.report_cache += wikipage_str
                self.report_cache += smwimportoverview.wikipage_content
            amount_terms = len(smwimportoverview.terms)
            if self.cli_arg_write is True:
                wiki_article_path = mwactions.get_articlepath()
                wikipage_name = wiki_article_path + wikipage_name  # adds url
            onto_report_line = f'{prefix} creates {wikipage_name} with' \
                               f' {amount_terms} terms\n'
            report += onto_report_line
        if self.output_file is True:
            self.report_cache += report
            write2file(filename='report.txt', content=self.report_cache)
        return report
