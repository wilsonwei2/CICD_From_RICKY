from xml.etree import ElementTree
from xml.dom import minidom
from xml.dom.minidom import Node

def remove_blanks_xml(node):
    """ Remove blank text nodes """

    for child_node in node.childNodes:
        if child_node.nodeType == Node.TEXT_NODE:
            if child_node.nodeValue:
                child_node.nodeValue = child_node.nodeValue.strip()
        elif child_node.nodeType == Node.ELEMENT_NODE:
            remove_blanks_xml(child_node)


def prettify_xml(elem):
    """ Prettify XML """

    rough_string = ElementTree.tostring(elem, "utf-8")
    reparsed = minidom.parseString(rough_string)
    remove_blanks_xml(reparsed)
    reparsed.normalize()
    return reparsed.toprettyxml(indent="    ")
