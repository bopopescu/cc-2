# Copyright (c) 2006,2007 Mitch Garnaat http://garnaat.org/
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

"""
Represents an EC2 Security Group
"""
from boto.ec2.ec2object import EC2Object
from boto.exception import BotoClientError

class SecurityGroup(EC2Object):
    
    def __init__(self, connection=None, owner_id=None,
                 name=None, description=None):
        EC2Object.__init__(self, connection)
        self.owner_id = owner_id
        self.name = name
        self.description = description
        self.rules = []

    def __repr__(self):
        return 'SecurityGroup:%s' % self.name

    def startElement(self, name, attrs, connection):
        if name == 'item':
            self.rules.append(IPPermissions(self))
            return self.rules[-1]
        else:
            return None

    def endElement(self, name, value, connection):
        if name == 'ownerId':
            self.owner_id = value
        elif name == 'groupName':
            self.name = value
        elif name == 'groupDescription':
            self.description = value
        elif name == 'ipRanges':
            pass
        elif name == 'return':
            if value == 'false':
                self.status = False
            elif value == 'true':
                self.status = True
            else:
                raise Exception(
                    'Unexpected value of status %s for group %s'%(
                        value, 
                        self.name
                    )
                )
        else:
            setattr(self, name, value)

    def delete(self):
        return self.connection.delete_security_group(self.name)

    def add_rule(self, ip_protocol, from_port, to_port,
                 src_group_name, src_group_owner_id, cidr_ip):
        rule = IPPermissions(self)
        rule.ip_protocol = ip_protocol
        rule.from_port = from_port
        rule.to_port = to_port
        self.rules.append(rule)
        rule.add_grant(src_group_name, src_group_owner_id, cidr_ip)

    def remove_rule(self, ip_protocol, from_port, to_port,
                    src_group_name, src_group_owner_id, cidr_ip):
        target_rule = None
        for rule in self.rules:
            if rule.ip_protocol == ip_protocol:
                if rule.from_port == from_port:
                    if rule.to_port == to_port:
                        target_rule = rule
                        target_grant = None
                        for grant in rule.grants:
                            if grant.name == src_group_name:
                                if grant.owner_id == src_group_owner_id:
                                    if grant.cidr_ip == cidr_ip:
                                        target_grant = grant
                        if target_grant:
                            rule.grants.remove(target_grant)
        if len(rule.grants) == 0:
            self.rules.remove(target_rule)

    def authorize(self, ip_protocol=None, from_port=None, to_port=None,
                  cidr_ip=None, src_group=None):
        """
        Add a new rule to this security group.
        You need to pass in either src_group_name
        OR ip_protocol, from_port, to_port,
        and cidr_ip.  In other words, either you are authorizing another
        group or you are authorizing some ip-based rule.
        
        :type ip_protocol: string
        :param ip_protocol: Either tcp | udp | icmp

        :type from_port: int
        :param from_port: The beginning port number you are enabling

        :type to_port: int
        :param to_port: The ending port number you are enabling

        :type to_port: string
        :param to_port: The CIDR block you are providing access to.
                        See http://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing

        :type src_group: :class:`boto.ec2.securitygroup.SecurityGroup` or
                         :class:`boto.ec2.securitygroup.GroupOrCIDR`
                         
        :rtype: bool
        :return: True if successful.
        """
        if src_group:
            from_port = None
            to_port = None
            cidr_ip = None
            ip_protocol = None
            src_group_name = src_group.name
            src_group_owner_id = src_group.owner_id
        else:
            src_group_name = None
            src_group_owner_id = None
        status = self.connection.authorize_security_group(self.name,
                                                          src_group_name,
                                                          src_group_owner_id,
                                                          ip_protocol,
                                                          from_port,
                                                          to_port,
                                                          cidr_ip)
        if status:
            self.add_rule(ip_protocol, from_port, to_port, src_group_name,
                          src_group_owner_id, cidr_ip)
        return status

    def revoke(self, ip_protocol=None, from_port=None, to_port=None,
               cidr_ip=None, src_group=None):
        if src_group:
            from_port=None
            to_port=None
            cidr_ip=None
            ip_protocol = None
            src_group_name = src_group.name
            src_group_owner_id = src_group.owner_id
        else:
            src_group_name = None
            src_group_owner_id = None
        status = self.connection.revoke_security_group(self.name,
                                                       src_group_name,
                                                       src_group_owner_id,
                                                       ip_protocol,
                                                       from_port,
                                                       to_port,
                                                       cidr_ip)
        if status:
            self.remove_rule(ip_protocol, from_port, to_port, src_group_name,
                             src_group_owner_id, cidr_ip)
        return status

    def copy_to_region(self, region, name=None):
        """
        Create a copy of this security group in another region.
        Note that the new security group will be a separate entity
        and will not stay in sync automatically after the copy
        operation.

        :type region: :class:`boto.ec2.regioninfo.RegionInfo`
        :param region: The region to which this security group will be copied.

        :type name: string
        :param name: The name of the copy.  If not supplied, the copy
                     will have the same name as this security group.
        
        :rtype: :class:`boto.ec2.securitygroup.SecurityGroup`
        :return: The new security group.
        """
        if region.name == self.region:
            raise BotoClientError('Unable to copy to the same Region')
        conn_params = self.connection.get_params()
        rconn = region.connect(**conn_params)
        sg = rconn.create_security_group(name or self.name, self.description)
        source_groups = []
        for rule in self.rules:
            grant = rule.grants[0]
            if grant.name:
                if grant.name not in source_groups:
                    source_groups.append(grant.name)
                    sg.authorize(None, None, None, None, grant)
            else:
                sg.authorize(rule.ip_protocol, rule.from_port, rule.to_port,
                             grant.cidr_ip)
        return sg

    def instances(self):
        instances = []
        rs = self.connection.get_all_instances()
        for reservation in rs:
            uses_group = [g.id for g in reservation.groups if g.id == self.name]
            if uses_group:
                instances.extend(reservation.instances)
        return instances

class IPPermissions:

    def __init__(self, parent=None):
        self.parent = parent
        self.ip_protocol = None
        self.from_port = None
        self.to_port = None
        self.grants = []

    def __repr__(self):
        return 'IPPermissions:%s(%s-%s)' % (self.ip_protocol,
                                            self.from_port, self.to_port)

    def startElement(self, name, attrs, connection):
        if name == 'item':
            self.grants.append(GroupOrCIDR(self))
            return self.grants[-1]
        return None

    def endElement(self, name, value, connection):
        if name == 'ipProtocol':
            self.ip_protocol = value
        elif name == 'fromPort':
            self.from_port = value
        elif name == 'toPort':
            self.to_port = value
        else:
            setattr(self, name, value)

    def add_grant(self, name=None, owner_id=None, cidr_ip=None):
        grant = GroupOrCIDR(self)
        grant.owner_id = owner_id
        grant.name = name
        grant.cidr_ip = cidr_ip
        self.grants.append(grant)
        return grant

class GroupOrCIDR:

    def __init__(self, parent=None):
        self.owner_id = None
        self.name = None
        self.cidr_ip = None

    def __repr__(self):
        if self.cidr_ip:
            return '%s' % self.cidr_ip
        else:
            return '%s-%s' % (self.name, self.owner_id)

    def startElement(self, name, attrs, connection):
        return None

    def endElement(self, name, value, connection):
        if name == 'userId':
            self.owner_id = value
        elif name == 'groupName':
            self.name = value
        if name == 'cidrIp':
            self.cidr_ip = value
        else:
            setattr(self, name, value)

