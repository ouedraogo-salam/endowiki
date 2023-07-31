<?php
/**
 * ARC2 JSON-LD Serializer.
 *
 * @author John Walker <john.walker@semaku.com>
 * @license W3C Software License and GPL
 * @homepage <https://github.com/semsol/arc2>
 */
ARC2::inc('RDFSerializer');

class ARC2_JSONLDSerializer extends ARC2_RDFSerializer
{
    public function __construct($a, &$caller)
    {
        parent::__construct($a, $caller);
    }

    public function __init()
    {
        parent::__init();
        $this->content_header = 'application/ld+json';
    }

    public function getTerm($v, $term = 's')
    {
        if (!is_array($v)) {
            if (preg_match('/^\_\:/', $v)) {
                return ('o' == $term) ? $this->getTerm(['value' => $v, 'type' => 'bnode'], 'o') : '"'.$v.'"';
            }

            return ('o' == $term) ? $this->getTerm(['value' => $v, 'type' => 'uri'], 'o') : '"'.$v.'"';
        }
        if (!isset($v['type']) || ('literal' != $v['type'])) {
            if ('o' != $term) {
                return $this->getTerm($v['value'], $term);
            }

            return '{ "@id" : "'.$this->jsonEscape($v['value']).'" }';
        }
        /* literal */
        $r = '{ "@value" : "'.$this->jsonEscape($v['value']).'"';
        $suffix = isset($v['datatype']) ? ', "@type" : "'.$v['datatype'].'"' : '';
        $suffix = isset($v['lang']) ? ', "@language" : "'.$v['lang'].'"' : $suffix;
        $r .= $suffix.' }';

        return $r;
    }

    public function jsonEscape($v)
    {
        if (function_exists('json_encode')) {
            return preg_replace('/^"(.*)"$/', '\\1', str_replace("\/", '/', json_encode($v)));
        }
        $from = ['\\', "\r", "\t", "\n", '"', "\b", "\f"];
        $to = ['\\\\', '\r', '\t', '\n', '\"', '\b', '\f'];

        return str_replace($from, $to, $v);
    }

    public function getSerializedIndex($index, $raw = 0)
    {
        $r = '';
        $nl = "\n";
        foreach ($index as $s => $ps) {
            $r .= $r ? ','.$nl.$nl : '';
            $r .= '  { '.$nl.'    "@id" : '.$this->getTerm($s);
            //$first_p = 1;
            foreach ($ps as $p => $os) {
                $r .= ','.$nl;
                $r .= '    '.$this->getTerm($p).' : [';
                $first_o = 1;
                if (!is_array($os)) {/* single literal o */
                    $os = [['value' => $os, 'type' => 'literal']];
                }
                foreach ($os as $o) {
                    $r .= $first_o ? $nl : ','.$nl;
                    $r .= '      '.$this->getTerm($o, 'o');
                    $first_o = 0;
                }
                $r .= $nl.'    ]';
            }
            $r .= $nl.'  }';
        }
        $r .= $r ? ' ' : '';

        return '['.$nl.$r.$nl.']';
    }
}
