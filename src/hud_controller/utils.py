import importlib
import logging
import pkgutil
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

def import_submodules(module):
    """Import all submodules of a module, recursively"""
    for _loader, module_name, _is_pkg in pkgutil.walk_packages(
            module.__path__, module.__name__ + '.'):
        importlib.import_module(module_name)


def merge_junits(junit_xmls: list[str]) -> tuple[str, bool]:
    """
    Merge multiple JUnit XML strings into a single valid JUnit XML.
    
    This function takes N valid JUnit XML strings and returns a single
    valid JUnit XML where all testsuite elements are merged together
    under a single testsuites root element, along with a boolean indicating
    full success (no failures or errors).
    
    Args:
        junit_xmls: List of JUnit XML strings to merge
        
    Returns:
        A tuple of (merged_junit_xml_string, full_success_boolean)
        full_success is True if there are no failures or errors
    """
    if not junit_xmls:
        return '<?xml version="1.0" encoding="UTF-8"?>\n<testsuites></testsuites>', True
    
    if len(junit_xmls) == 1:
        xml_str = junit_xmls[0]
        try:
            root = ET.fromstring(xml_str)
            total_failures = 0
            total_errors = 0
            
            testsuites = root.findall('.//testsuite')
            if root.tag == 'testsuite':
                testsuites.append(root)
            
            for testsuite in testsuites:
                total_failures += int(testsuite.attrib.get('failures', 0))
                total_errors += int(testsuite.attrib.get('errors', 0))
            
            full_success = (total_failures == 0 and total_errors == 0)
            return xml_str, full_success
        except ET.ParseError:
            return xml_str, False
    
    merged_root = ET.Element('testsuites')
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    total_time = 0.0
    
    for xml_str in junit_xmls:
        if not xml_str or not xml_str.strip():
            continue
            
        try:
            root = ET.fromstring(xml_str)
            
            testsuites = root.findall('.//testsuite')
            
            if root.tag == 'testsuite':
                testsuites.append(root)
            
            for testsuite in testsuites:
                cloned_testsuite = ET.SubElement(merged_root, 'testsuite')
                
                for key, value in testsuite.attrib.items():
                    cloned_testsuite.set(key, value)
                
                for child in testsuite:
                    cloned_testsuite.append(child)
                
                if 'tests' in testsuite.attrib:
                    total_tests += int(testsuite.attrib.get('tests', 0))
                if 'failures' in testsuite.attrib:
                    total_failures += int(testsuite.attrib.get('failures', 0))
                if 'errors' in testsuite.attrib:
                    total_errors += int(testsuite.attrib.get('errors', 0))
                if 'skipped' in testsuite.attrib:
                    total_skipped += int(testsuite.attrib.get('skipped', 0))
                if 'time' in testsuite.attrib:
                    try:
                        total_time += float(testsuite.attrib.get('time', 0))
                    except ValueError:
                        pass
                        
        except ET.ParseError as e:
            logger.warning(f"Failed to parse JUnit XML: {e}")
            continue
    
    merged_root.set('tests', str(total_tests))
    merged_root.set('failures', str(total_failures))
    merged_root.set('errors', str(total_errors))
    merged_root.set('skipped', str(total_skipped))
    merged_root.set('time', str(total_time))
    
    xml_str = ET.tostring(merged_root, encoding='unicode')
    
    full_success = (total_tests > 0 and total_skipped < total_tests and total_failures == 0 and total_errors == 0)
    
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}', full_success