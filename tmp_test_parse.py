import sys, pathlib, xml.etree.ElementTree as ET
sys.path.append(str(pathlib.Path(__file__).resolve().parents[0] / 'src'))
from parse_xml import extract_event
xml = '''<?xml version="1.0" encoding="UTF-8"?>
<item>
    <venue>
        <address_1>14 Masonic St</address_1>
        <state>MA</state>
        <zip>01060</zip>
        <lat>42.317978</lat>
        <repinned>False</repinned>
        <name>packards- library room</name>
        <city>Northampton</city>
        <id>802416</id>
        <country>us</country>
        <lon>-72.633087</lon>
    </venue>
    <status>past</status>
    <description>Just general conversation about everything related to technology, science and the interwebs:<br /><br />ie.<br />opportunity to share information, field questions and discuss a variety of topics related to web development, programming, project management, software, visual design, etc. including CSS and others.<br /></description>
    <event_hosts>
        <event_hosts_item>
            <member_name>Leah</member_name>
            <member_id>2960740</member_id>
        </event_hosts_item>
    </event_hosts>
    <maybe_rsvp_count>2</maybe_rsvp_count>
    <waitlist_count>0</waitlist_count>
    <updated>1273444652000</updated>
    <rating>
        <average>4.0</average>
        <count>1</count>
    </rating>
    <group>
        <who>Developers</who>
        <join_mode>open</join_mode>
        <urlname>nohowebdev</urlname>
        <id>540457</id>
        <group_lat>42.3199996948</group_lat>
        <group_lon>-72.6399993896</group_lon>
        <name>Northampton Web Developers/ Web Designers Meetup Group</name>
    </group>
    <yes_rsvp_count>7</yes_rsvp_count>
    <created>1268091163000</created>
    <visibility>public</visibility>
    <name>General Meeting: tips and tricks for web developers, web designers &amp; programers</name>
    <id>12821780</id>
    <headcount>7</headcount>
    <utc_offset>-14400000</utc_offset>
    <time>1273271400000</time>
    <event_url>http://www.meetup.com/nohowebdev/events/12821780/</event_url>
    <photo_url>http://photos1.meetupstatic.com/photos/event/1/0/5/b/global_11476187.jpeg</photo_url>
</item>'''
root = ET.fromstring(xml)
doc = extract_event(root)
print('doc_id=', doc['doc_id'])
print('title=', doc['title'])
print('group=', doc['group'], 'urlname=', doc['group_urlname'])
print('venue=', doc['venue'])
print('hosts=', doc['hosts'])
print('time=', doc['time'], 'created=', doc['created'], 'updated=', doc['updated'])
print('event_url=', doc['event_url'])
print('text_prefix=', doc['text'][:120])
