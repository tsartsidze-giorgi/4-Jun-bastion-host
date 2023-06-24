from auth import aws_client
from vpc import create_vpc, add_name_tag, get_or_set_igw, create_route_table_without_route, create_subnet, associate_route_table_to_subnet, create_route_table_with_route, enable_auto_public_ips
from ec2 import create_key_pair, create_security_group, add_ssh_access_sg, run_ec2
from rds import create_db_subnet_group, create_rds_security_group, create_db_instance
import time
from os import getenv
from dotenv import load_dotenv
import argparse
load_dotenv()
parser = argparse.ArgumentParser()
parser.add_argument('--vpc_name', "-vpcN", type=str, help='vpc name')
parser.add_argument('--subnet_name', "-sn", type=str, help='subnet name')
parser.add_argument('--key_name', "-kn", type=str, help='key pair name')
parser.add_argument('--ec2_name', "-ec2n", type=str, help='ec2 name')
parser.add_argument('--create_bastion_host',
                    '-cbh',
                    nargs='?',
                    const='true',
                    help='create bastion host instance')
args = parser.parse_args()


def main(vpc_name, subnet_name, key_name, ec2_name):
  client = aws_client('ec2')

  vpc_id = create_vpc(client, '10.0.0.0/16')
  add_name_tag(client, vpc_id, vpc_name)
  get_or_set_igw(client, vpc_id)

  private_subnets = []
  # create private subnet
  subnet_id = create_subnet(client, vpc_id, '10.0.0.0/24',
                            f'private_{subnet_name}_1', 'us-east-1a')
  rtb_id = create_route_table_without_route(client, vpc_id)
  associate_route_table_to_subnet(client, rtb_id, subnet_id)
  private_subnets.append(subnet_id)

  subnet_id = create_subnet(client, vpc_id, '10.0.1.0/24',
                            f'private_{subnet_name}_2', 'us-east-1b')
  rtb_id = create_route_table_without_route(client, vpc_id)
  time.sleep(5)
  associate_route_table_to_subnet(client, rtb_id, subnet_id)
  private_subnets.append(subnet_id)
  print(f'private subnets : {private_subnets}')
  # public subnet
  subnet_id = create_subnet(client, vpc_id, '10.0.2.0/24',
                            f'public_{subnet_name}_1', 'us-east-1a')
  rtb_id = create_route_table_with_route(client, vpc_id, 'my_route_name',
                                         get_or_set_igw(client, vpc_id))
  time.sleep(5)
  associate_route_table_to_subnet(client, rtb_id, subnet_id)
  enable_auto_public_ips(client, subnet_id, 'enable')

  # create key pair
  create_key_pair(client, key_name)

  # create ec2 sg
  ec2_security_group_id = create_security_group(
    client, f'{ec2_name}-sg', "Security group to enable access on ec2", vpc_id)

  # only concrete ip rule
  add_ssh_access_sg(client, ec2_security_group_id)

  # EC2
  run_ec2(client, ec2_security_group_id, subnet_id, ec2_name)

  # RDS - Postgres
  rds_client = aws_client('rds')

  security_group_name = f'{ec2_name}automated-sg-rds'

  # SG for RDS

  rds_subnet_group = create_db_subnet_group(rds_client, security_group_name,
                                            vpc_id, private_subnets)
  print("switched to ec2")
  rds_sg_id = create_rds_security_group(aws_client('ec2'), security_group_name,
                                        vpc_id, ec2_security_group_id)

  create_db_instance(rds_client, rds_sg_id, rds_subnet_group)


if args.create_bastion_host:
  main(args.vpc_name, args.subnet_name, args.key_name, args.ec2_name)
