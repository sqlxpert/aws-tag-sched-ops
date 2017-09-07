# Start, Reboot, Stop and Back Up AWS Resources Using Tags

## Benefits

* This Python-based AWS Lambda function **saves money** by stopping resources during off-hours.
* It also **improves operational reliability** by taking frequent backups.
* It uses simple, **tag-based schedules**.
* It defines a set of Identity and Access Management (IAM) policies for **security**.

## Resources and Operations

|AWS Resource|Start|Create Image|Reboot, Create Image|Reboot|Create Snapshot|Create Snapshot, Stop|Stop|
|--|--|--|--|--|--|--|--|
|EC2 compute instance|&#x2713;|&#x2713;|&#x2713;|&#x2713;| | | |
|EC2 EBS disk volume| | | | |&#x2713;| | |
|RDS database instance|&#x2713;| | |&#x2713;|&#x2713;|&#x2713;|&#x2713;|

## Quick Start ##

1. Log in to the [AWS Console](https://signin.aws.amazon.com/console)

   For demonstration purposes _only_, it is easiest to log in as an IAM user with full privileges for:
     * CloudFormation
     * IAM
     * Lambda
     * EC2
     * RDS
 
   (For routine usage, see [Security Model](#security-model))

2. Navigate to the [CloudFormation Console](https://console.aws.amazon.com/cloudformation/home)
3. Create stacks from these templates, in the order listed:
     1. [`placeholder.yaml`](placeholder.yaml)
     2. [`placeholder.yaml`](placeholder.yaml)
4. Navigate to [Instances](https://console.aws.amazon.com/ec2/v2/home#Instances) in the EC2 Console
5. Select an instance, open the Tags tab, and click Add/Edit Tags
6. Add the following tags:

   |Key|Value|Note|
   |--|--|--|
   |`managed-image`||Leave value blank|
   |`managed-image-periodic`|`d=*,H:M=11:30`|Replace `11:30` with [current UTC time](https://www.timeanddate.com/worldclock/timezone/utc) + 15 minutes|

7. Navigate to [AMIs](https://console.aws.amazon.com/ec2/v2/home#Images) in the EC2 Console
8. After approximately 20 minutes, check for a newly-created image

## Security Model

### IAM, EC2 and RDS Constraints

 * Restricting **instance, volume, image and snapshot tagging privileges** is crucial, because tags determine what gets backed up and/or rebooted, and when, as well as which backups are protected from deletion.
 * The right to _add_ tags to EC2 or RDS resources includes the right to _change_ the values of existing tags.
 * Although it is possible to restrict tagging privileges to RDS resources that already have particular tags, the _results_ of an RDS tagging call are not checked.
  * It is not possible to require that particular tags be applied to EC2 instance images, EBS volume snapshots, or RDS instance snapshots, upon creation.

 * Restricting **reboot privileges** is crucial. Reboots clear ephemeral data (such as cache) and may make services unavailable. A service might even fail to start after a reboot.
 * Denying EC2 instance reboot privileges does not prevent forcing a reboot as part of an image creation call.

 * Restricting RDS **database snapshot** privileges is crucial. An RDS snapshot might degrade database performance and block RDS instance modifications for a long period of time.

### Consequences

 * Support for positive tags (e.g., "yes, reboot") as well as negative ones (e.g., "no, do not reboot") is a necessary compromise.
 * Where a positive and a negative tag conflict, the safer interpretation prevails.

 * Different IAM managed policies are provided for:
     * Ad-hoc tagging (`TagAddChange`). These policies confer the right to add and change tags but deny the right to delete tags. Because `Deny` takes precedence over `Allow` in IAM, these policies have the side-effect of preventing users -- even administrators -- from deleting certain tags from any EC2 instance, EC2 instance snapshot, or EBS volume, and any tag from any RDS instance or snapshot, as applicable.
     * Administrative tagging (`TagAdmin`). These policies confer the right to add, change and delete tags.
 * Your organization's tagging controls might be different. The `Tag` policies are provided only as a starting point.
 
 * Administrative tagging rights must never be combined with the right to modify the source code of the AWS Lambda function that creates images and snapshots and initiates reboots. The code serves as a security barrier. It is designed to respect tags that forbid reboot and to apply tags that forbid deletion.

## Licensing

|Scope|License|
|---|---|
|Source code files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|
|Source code within documentation files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|
|Documentation files|[GNU Free Documentation License (FDL) 1.3](http://www.gnu.org/licenses/fdl-1.3.html)|

Paul Marcelin, 2017
