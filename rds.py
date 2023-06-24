def create_db_subnet_group(rds_client, subnet_group_name, vpc_id, subnet_ids):
  description = "auto-description"
  response = rds_client.create_db_subnet_group(
    DBSubnetGroupName=subnet_group_name,
    DBSubnetGroupDescription=description,
    SubnetIds=subnet_ids)

  print(f"DB subnet group {subnet_group_name} has been created successfully.")
  return response['DBSubnetGroup'].get("DBSubnetGroupName")


def create_rds_security_group(ec2_client, security_group_name, vpc_id,
                              ec2_security_group_id):
  source_security_group_id = ec2_security_group_id
  try:
    response = ec2_client.describe_security_groups(
      GroupNames=[security_group_name])
    security_group_id = response['SecurityGroups'][0]['GroupId']
    print(
      f"Security Group {security_group_name} already exists with ID {security_group_id}"
    )
  except ec2_client.exceptions.ClientError as e:
    if e.response['Error']['Code'] == 'InvalidGroup.NotFound':
      response = ec2_client.create_security_group(
        GroupName=security_group_name,
        Description='Security Group for RDS',
        VpcId=vpc_id)
      security_group_id = response['GroupId']
      print(
        f"Security Group {security_group_name} created with ID {security_group_id}"
      )
    else:
      raise e

  ec2_client.authorize_security_group_ingress(
    GroupId=security_group_id,
    IpPermissions=[
      {
        'IpProtocol': 'tcp',
        'FromPort': 5432,
        'ToPort': 5432,
        'UserIdGroupPairs': [
          {
            'GroupId': source_security_group_id,
          },
        ],
      },
    ],
  )

  return security_group_id


def create_db_instance(rds_client, security_group_id, subnet_group_name):
  response = rds_client.create_db_instance(
    DBName='postgres',
    DBInstanceIdentifier='automated-pg-db-1',
    AllocatedStorage=50,
    DBInstanceClass='db.t4g.micro',
    Engine='postgres',
    MasterUsername='postgres',
    MasterUserPassword='strongrandompassword',
    VpcSecurityGroupIds=[security_group_id],
    DBSubnetGroupName=subnet_group_name,
    BackupRetentionPeriod=7,
    Port=5432,
    MultiAZ=False,
    EngineVersion='14.7',
    AutoMinorVersionUpgrade=True,
    # Iops=123, # Necessary when StorageType is 'io1'
    PubliclyAccessible=False,
    Tags=[
      {
        'Key': 'Name',
        'Value': 'automated Postgre'
      },
    ],
    StorageType='gp2',
    EnablePerformanceInsights=True,
    PerformanceInsightsRetentionPeriod=7,
    DeletionProtection=False,
  )

  db_instance_id = response['DBInstance']['DBInstanceIdentifier']
  print("waiting for db avaliable:")
  waiter = rds_client.get_waiter('db_instance_available')
  waiter.wait(DBInstanceIdentifier=db_instance_id)
  print(f"RDS instance {db_instance_id} was created")
