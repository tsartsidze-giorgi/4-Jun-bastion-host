import time


### part 1/2 ###
def list_vpcs(ec2_client):
  result = ec2_client.describe_vpcs()
  vpcs = result.get("Vpcs")
  print(vpcs)


def create_vpc(ec2_client, cidr):
  vpc = ec2_client.create_vpc(CidrBlock="10.0.0.0/16")
  vpc_id = vpc['Vpc']['VpcId']
  waiter = ec2_client.get_waiter('vpc_available')
  waiter.wait(VpcIds=[vpc_id])
  print(f'vpc_id: {vpc_id}')
  return vpc_id


def add_name_tag(ec2_client, vpc_id, name):
  ec2_client.create_tags(Resources=[vpc_id],
                         Tags=[{
                           "Key": "Name",
                           "Value": name
                         }])


def attach_igw_to_vpc(ec2_client, vpc_id, igw_id):
  ec2_client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)


### part 2/2 ###


def create_subnet(ec2_client, vpc_id, cidr_block, subnet_name,
                  availability_zone):
  response = ec2_client.create_subnet(VpcId=vpc_id,
                                      CidrBlock=cidr_block,
                                      AvailabilityZone=availability_zone)
  subnet = response.get("Subnet")
  # pprint(subnet)
  subnet_id = subnet.get("SubnetId")
  waiter = ec2_client.get_waiter('subnet_available')
  waiter.wait(SubnetIds=[subnet_id])
  time.sleep(3)
  print("wait")
  ec2_client.create_tags(
    Resources=[subnet_id],
    Tags=[
      {
        "Key": "Name",
        "Value": subnet_name
      },
    ],
  )
  return subnet_id


def get_or_set_igw(ec2_client, vpc_id):
  igw_id = None
  igw_response = ec2_client.describe_internet_gateways(
    Filters=[{
      'Name': 'attachment.vpc-id',
      'Values': [vpc_id]
    }])

  if 'InternetGateways' in igw_response and igw_response['InternetGateways']:
    igw = igw_response['InternetGateways'][0]
    igw_id = igw['InternetGatewayId']
  else:
    response = ec2_client.create_internet_gateway()
    # pprint(response)
    igw = response.get("InternetGateway")
    igw_id = igw.get("InternetGatewayId")
    response = ec2_client.attach_internet_gateway(InternetGatewayId=igw_id,
                                                  VpcId=vpc_id)
    print("attached")
    # pprint(response)
  return igw_id


def create_route_table_with_route(ec2_client, vpc_id, route_table_name,
                                  igw_id):
  response = ec2_client.create_route_table(VpcId=vpc_id)
  route_table = response.get("RouteTable")
  # pprint(route_table)
  route_table_id = route_table.get("RouteTableId")
  print("Route table id", route_table_id)
  ec2_client.create_tags(
    Resources=[route_table_id],
    Tags=[
      {
        "Key": "Name",
        "Value": route_table_name
      },
    ],
  )
  response = ec2_client.create_route(
    DestinationCidrBlock='0.0.0.0/0',
    GatewayId=igw_id,
    RouteTableId=route_table_id,
  )
  return route_table_id


def associate_route_table_to_subnet(ec2_client, route_table_id, subnet_id):
  ec2_client.associate_route_table(RouteTableId=route_table_id,
                                   SubnetId=subnet_id)
  print("Route table associated")
  # pprint(response)


def enable_auto_public_ips(ec2_client, subnet_id, action):
  new_state = True if action == "enable" else False
  response = ec2_client.modify_subnet_attribute(
    MapPublicIpOnLaunch={"Value": new_state}, SubnetId=subnet_id)
  print("Public IP association state changed to", new_state)


def create_route_table_without_route(ec2_client, vpc_id):
  response = ec2_client.create_route_table(VpcId=vpc_id)
  route_table = response.get("RouteTable")
  route_table_id = route_table.get("RouteTableId")
  wait_for_route_table(ec2_client, route_table_id)
  print("Route table id", route_table_id)
  ec2_client.create_tags(
    Resources=[route_table_id],
    Tags=[
      {
        "Key": "Name",
        "Value": "private-route-table"
      },
    ],
  )
  return route_table_id


def wait_for_route_table(ec2_client, route_table_id, max_retries=10):
  retries = 0
  while retries < max_retries:
    try:
      response = ec2_client.describe_route_tables(
        RouteTableIds=[route_table_id])
      route_tables = response.get('RouteTables')
      if route_tables and len(route_tables) > 0:
        print(f"Route table with ID '{route_table_id}' exists.")
        return
      else:
        print(f"Route table with ID '{route_table_id}' not found. Retrying...")
        print(f"Response from describe_route_tables: {response}")
    except ec2_client.exceptions.ClientError as e:
      error_code = e.response['Error']['Code']
      if error_code == 'InvalidRouteTableID.NotFound':
        retries += 1
        print(f"Route table with ID '{route_table_id}' not found. Retrying...")
    time.sleep(5)
  raise ValueError(f"Route table with ID '{route_table_id}' does not exist")
