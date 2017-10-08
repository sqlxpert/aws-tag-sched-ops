# Start, Reboot, Stop and Back Up AWS Resources with Tags

## Benefits

* **Save money** by stopping EC2 instances and RDS databases during off-hours
* **Take backups** more frequently
* **Use tags** to schedule operations
* Secure tags and backups using Identity and Access Management (IAM) policies
* Install and update easily, with CloudFormation (and optionally, StackSets)

Jump to: [Installation](#quick-start) &bull; [Operation Tags](#enabling-operations) &bull; [Schedule Tags](#scheduling-operations) &bull; [Logging](#output) &bull; [Security](#security-model) &bull; [Multi-region/multi-account](#advanced-installation)

## Quick Start

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console) as a privileged user.

   _Security Tip:_ To see what you'll be installing, look in the [CloudFormation template](/cloudformation/aws_tag_sched_ops.yaml). <br/>`grep 'Type: "AWS::' aws_tag_sched_ops.yaml | sort | uniq` works well.
   
2. Go to [Instances](https://console.aws.amazon.com/ec2/v2/home#Instances) in the EC2 Console. Right-click the Name or ID of an instance, select Instance Settings, and then select Add/Edit Tags. Add:

   |Key|Value|Note|
   |--|--|--|
   |`managed-image`||Leave value blank|
   |`managed-image-periodic`|`d=*,H:M=11:30`|Replace `11:30` with [current UTC time](https://www.timeanddate.com/worldclock/timezone/utc) + 15 minutes|

3. Go to the [S3 Console](https://console.aws.amazon.com/s3/home). Click the name of the bucket where you keep AWS Lambda function source code. (This may be the same bucket where you keep CloudFormation templates.) If you are creating the bucket now, be sure to create it in the region where you intend to install TagSchedOps; appending the region to the bucket name (for example, `my-bucket-us-east-1`) is recommended. Upload the compressed source code of the AWS Lambda function, [`aws_tag_sched_ops_perform.py.zip`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws_tag_sched_ops_perform.py.zip)

   _Security Tip:_ Remove public read and write access from the S3 bucket. Carefully limit write access.

   _Security Tip:_ Download the file from S3 and verify it. (In some cases, you can simply compare the ETag reported by S3.)<br/>`md5sum aws_tag_sched_ops_perform.py.zip` should yield `63743f89e05b89b4f6eb14ca7eedecc1`

4. Go to the [CloudFormation Console](https://console.aws.amazon.com/cloudformation/home). Click Create Stack. Click Choose File, immediately below "Upload a template to Amazon S3", and navigate to your locally downloaded copy of [`cloudformation/aws_tag_sched_ops.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

   |Item|Value|
   |--|--|
   |Stack name|`TagSchedOps`|
   |LambdaCodeS3Bucket|Name of your S3 bucket|
   |MainRegion|Current region, if other than `us-east-1`|

   For all other paramters, keep the default values.
   
5. After 20 minutes, check [Images](https://console.aws.amazon.com/ec2/v2/home#Images:sort=desc:creationDate) in the EC2 Console.

6. Before deregistering (deleting) the sample image, note its ID, so that you can delete the associated [Snapshots](https://console.aws.amazon.com/ec2/v2/home#Snapshots:sort=desc:startTime). Also untag the instance.

7. Go to [Users](https://console.aws.amazon.com/iam/home#/users) in the IAM Console. Click your regular (uprivileged) username. Click Add Permissions, then click "Attach existing policies directly". In the Search box, type `TagSchedOpsAdminister`. Add the two matching policies.
      
   _Security Tip_: Review EC2 and RDS tagging privileges for all entities.

8. Log out of the AWS Console. You can now manage relevant tags, view logs, and decode errors, without logging in as a privileged user.

## Warnings

 * Check that scheduled AWS operations have completed successfully. Verification of completion is beyond the scope of this code.
 
 * Test your backups! Can they be restored successfully?
 
 * Weigh the benefits of rebooting against the risks. Rebooting is usually necessary to make software updates take effect, but a system may stop working afterward.
 
 * Be aware of AWS charges, including but not limited to: the costs of running the AWS Lambda function, storing CloudWatch logs, and storing images and snapshots; the whole-hour cost when you stop an RDS, EC2 Windows, or EC2 commercial Linux instance (but [most EC2 instances have a 1-minute minimum charge](https://aws.amazon.com/blogs/aws/new-per-second-billing-for-ec2-instances-and-ebs-volumes/)); the continuing cost of storage for stopped instances; and costs that resume when AWS automatically starts an RDS instance that has been stopped for too many days.
 
 * Secure your own AWS environment. Test the function and the IAM policies from end-to-end, to make sure that they work correctly and meet your expectations. To help improve this project, please submit [bug reports and feature requests](https://github.com/sqlxpert/aws-tag-sched-ops/issues), as well as [proposed changes](https://github.com/sqlxpert/aws-tag-sched-ops/pulls).

## Enabling Operations

* To enable an operation, add a tag from the table. Leave the value blank.

  | |Start|Create Image|Reboot then Create Image|Reboot then Fail Over|Reboot|Create Snapshot|Create Snapshot then Stop|Stop|
  |--|--|--|--|--|--|--|--|--|
  |EC2 compute instance|`managed-start`|`managed-image`|`managed-reboot-image`| |`managed-reboot`| | |`managed-stop`|
  |EC2 EBS disk volume| | | | | |`managed-snapshot`| | |
  |RDS database instance|`managed-start`| | |`managed-reboot-failover`|`managed-reboot`|`managed-snapshot`|`managed-snapshot-stop`|`managed-stop`|

* Also add tags for [repetitive (`-periodic`)](#repetitive-schedules) and/or [one-time (`-once`)](#one-time-schedules) schedules. Prefix with the operation.
* If there are no corresponding schedule tags, an enabling tag will be ignored, and the operation will never occur.
* To temporarily suspend an operation, delete its enabling tag. You may leave its schedule tag(s) in place.
* Examples (for an EC2 or RDS instance):

  |Set of Tags|Works?|Comment|
  |--|--|--|
  |`managed-start` <br/>`managed-start-periodic`=`u=1,H=09,M=05`|Yes|Enabled and scheduled|
  |`managed-start`=`No` <br/>`managed-start-periodic`=`u=1,H=09,M=05`|Yes|Value of enabling tag is always ignored|
  |`managed-start` <br/>`managed-start-once`=`2017-12-31T09:05`|Yes||
  |`managed-start` <br/>`managed-start-periodic`=`u=1,H=09,M=05` <br/>`managed-start-once`=`2017-12-31T09:05`|Yes|Both repetitive and one-time schedule tags are allowed|
  |`managed-start`|No|No schedule tag|
  |`managed-start-once`=`2017-12-31T09:05`|No|No enabling tag (operation is suspended)|
  |`managed-start` <br/>`managed-start-once`|No|Blank schedule|
  |`managed-start` <br/>`managed-start-periodic`=`Monday`|No|Invalid schedule|
  |`managed-start` <br/>`managed-stop-periodic`=`u=1,H=09,M=05`|No|Enabling tag and schedule tag cover different operations|

## Scheduling Operations
 
 * All times are UTC, on a 24-hour clock.
 * The function runs once every 10 minutes. The last digit of the minute is always ignored. For example, `M=47` means _one time, between 40 and 50 minutes after the hour_.
 * Month and minute values must have two digits. Use a leading zero if necessary. (Weekday numbers have only one digit.)
 * Use a comma (`,`) _without spaces_ to separate components. The order of components within a tag value does not matter.
 * `T` separates day information from time; it is not a variable.
 * [Repetitive (`-periodic`)](#repetitive-schedules) and [one-time (`-once`)](#one-time-schedules) schedule tags are supported. Prefix with the operation.
 * If the corresponding [enabling tag](#enabling-operations) is missing, schedule tags will be ignored, and the operation will never occur.

### Repetitive Schedules

  * Tag suffix: `-periodic`

  * Values: one or more of the following components:

    |Name|Minimum|Maximum|Wildcard|Combines With|
    |--|--|--|--|--|
    |Day of month (`d`)|`d=01`|`d=31`|`d=*`|`H` and `M`, or `H:M`|
    |Weekday (`u`)|`u=1` (Monday)|`u=7` (Sunday)||`H` and `M`, or `H:M`|
    |Hour (`H`)|`H=00`|`H=23`|`H=*`|`d` or `u`, and `M`|
    |Minute (`M`)|`M=00`|`M=59`||`d` or `u`, and `H`|
    |Hour and minute (`H:M`)|`H:M=00:00`|`H:M=23:59`||`d` or `u`|
    |Day of month, hour and minute (`dTH:M`)|`dTH:M=01T00:00`|`dTH:M=31T23:59`|||
    |Weekday, hour and minute (`uTH:M`)|`uTH:M=1T00:00`|`uTH:M=7T23:59`|||
    
      * To be valid, a component or combination of components must specify a day, hour and minute.
      * Repeat a whole component to specify multiple values. For example, `d=01,d=11,d=21` means the 1st, 11th and 21st days of the month.
      * The `*` wildcard is allowed for day (_every day of the month_) and hour (_every hour of the day_).
      * For consistent one-day-a-month scheduling, avoid `d=29` through `d=31`.
      * Label letters are from [`strftime`](http://manpages.ubuntu.com/manpages/xenial/man3/strftime.3.html) and weekday numbers are [ISO 8601-standard](https://en.wikipedia.org/wiki/ISO_8601#Week_dates) (different from `cron`).

  * Examples:
  
    |Value of `-periodic` Schedule Tag|Demonstrates|Operation Begins|
    |--|--|--|
    |`d=28,H=14,M=25` _or_ `dTH:M=28T14:25`|Monthly event|Between 14:20 and 14:30 on the 28th day of every month.|
    |`d=1,d=8,d=15,d=22,H=03,H=19,M=01`|`cron`-style schedule|Between 03:00 and 03:10 and again between 19:00 and 19:10, on the 1st, 8th, 15th, and 22nd days of every month.|
    |`d=*,H=*,M=15,M=45,H:M=08:50`|Extra event in the day|Between 10 and 20 minutes after the hour and 40 to 50 minutes after the hour, every hour of every day, _and also_ every day between 08:50 and 09:00.|
    |`d=*,H=11,M=00,uTH:M=2T03:30,uTH:M=5T07:20`|Extra weekly events|Between 11:00 and 11:10 every day, _and also_ every Tuesday between 03:30 and 03:40 and every Friday between 07:20 and 7:30.|
    |`u=3,H=22,M=15,dTH:M=01T05:20`|Extra monthly event|Between 22:10 and 22:20 every Wednesday, _and also_ on the first day of every month between 05:20 and 05:30.|
    
### One-Time Schedules
 
  * Tag suffix: `-once`

  * Values: one or more [ISO 8601 combined date and time strings](https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations), of the form `2017-03-21T22:40` (March 21, 2017, in this example)
      * Remember, the code runs once every 10 minutes and the last digit of the minute is ignored
      * Omit seconds and fractions of seconds
      * Omit time zone

## Output

* After logging in to the [AWS Web Console](https://signin.aws.amazon.com/console), go to the [Log Group for the AWS Lambda function](https://console.aws.amazon.com/cloudwatch/home#logs:prefix=/aws/lambda/TagSchedOps-TagSchedOpsPerformLambdaFn-), in the CloudWatch Logs Console. If you gave the CloudFormation stack a name other than `TagSchedOps`, check the list of [Log Groups for _all_ AWS Lambda functions](https://console.aws.amazon.com/cloudwatch/home#logs:prefix=/aws/lambda/) instead.

* Sample output:

  |`initiated`|`svc`|`rsrc_type`|`rsrc_id`|`op`|`child_rsrc_type`|`child`|`child_op`|`note`|
  |--|--|--|--|--|--|--|--|--|
  |`9`||||||||`2017-09-12T20:40`|
  |`1`|`ec2`|`Instance`|`i-08abefc70375d36e8`|`reboot-image`|`Image`|`zm-my-server-20170912T2040-83xx7`|||
  |`1`|`ec2`|`Instance`|`i-08abefc70375d36e8`|`reboot-image`|`Image`|`ami-bc9fcbc6`|`tag`||
  |`1`|`ec2`|`Instance`|`i-04d2c0140da5bb13e`|`start`|||||
  |`0`|`ec2`|`Instance`|`i-09cdea279388d35a2`|`start,stop`||||`OPS_UNSUPPORTED`|
  |`0`|`rds`|`DBInstance`|`my-database`|`reboot-failover`||||...`ForceFailover cannot be specified`...|
  
  _This run began September 12, 2017 between 20:40 and 20:50 UTC. An EC2 instance is being rebooted and backed up, but the instance may not yet be ready again, and the image may not yet be complete; the image is named `zm-my-server-20170912T2040-83xx7`. The image has received ID `ami-bc9fcbc6`, and has been tagged. A different EC2 instance is starting up, but may not yet be ready. A third EC2 instance is tagged for simultaneous start and stop, a combination that is not supported. An RDS database instance could not be rebooted with fail-over. (The full error message goes on to explain that it is not multi-zone.)_

* There is a header line, an information line, and one line for each operation requested. (Tagging is usually a separate operation.)

* Values are tab-separated (but the CloudWatch Logs Console seems to collapse multiple tabs).

* Columns and standard values:

  |`initiated`|`svc`|`rsrc_type`|`rsrc_id`|`op`|`child_rsrc_type`|`child`|`child_op`|`note`|
  |--|--|--|--|--|--|--|--|--|
  |Operation initiated?|Service|Resource type|Resource ID|Operation|Child type|Pointer to child|Child operation|Message|
  |`0`&nbsp;No <br/>`1`&nbsp;Yes <br/>`9`&nbsp;_Info._|`ec2` <br/>`rds`|`Instance` <br/>`Volume` <br/>`DBInstance`||_See_ [_table_](#enabling-operations)|`Image` <br/>`Snapshot`|_Name, ID, or ARN, as available_|`tag`||

* Although the TagSchedOpsAdminister and TagSchedOpsTagSchedule policies authorize read-only access to the logs via the AWS API, and seem to be sufficient for using the links provided above, users who are not AWS administrators may also want [additional privileges for the CloudWatch Console](http://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/iam-identity-based-access-control-cwl.html#console-permissions-cwl).

### Debugging Mode

If the `DEBUG` environment variable is set, the function outputs internal `parent_params` reference data, including the regular expressions used to match schedule tags.
    
To use the debugging mode,

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console) as a privileged user. AWS Lambda treats changes to environment variables like changes to code.
    
2. Click on the [TagSchedOpsPerformLambdaFn AWS Lambda function](https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions?f0=a3c%3D%3AVGFnU2NoZWRPcHNQZXJmb3JtTGFtYmRhRm4%3D).
    
3. Open the Code tab and scroll to the bottom. In the "Environment variables" section, type `DEBUG` in the first empty Key box. Leave Value blank.
    
4. <a name="debug-step-4"></a>Scroll back to the top and click the white Save button. _Do not click the orange "Save and test" button_; that would cause the function to run more than once in the same 10-minute interval.
    
5. After 10 minutes, find the debugging information in [CloudWatch Logs](#output).
    
6. Turn off debugging mode right away, because the extra information is lengthy. Back on the Code tab, scroll down and click Remove, to the far right of `DEBUG`. Repeat [Step 4](#debug-step-4) to save.

## Master On/Off Switch

* The TagSchedOpsAdminister policies authorize turning the function on or off completely.

* After logging in to the [AWS Web Console](https://signin.aws.amazon.com/console), go to [Rules](https://console.aws.amazon.com/cloudwatch/home#rules:) in the CloudWatch Events Console. Click the radio button to the left of TagSchedOpsPerform10MinEventRule, then select Enable or Disable from the Actions pop-up menu, next to the blue "Create rule" button.

* This toggle is per-region and per-AWS-account.

* Missed operations will not occur when the function is turned back on; there is no queue or backlog.

## Child Resources

Some operations create a child resource (image or snapshot) from a parent resource (instance or volume).
 
### Naming

* The name of the child consists of these parts, separated by hyphens (`-`):

  |#|Part|Example|Purpose|
  |--|--|--|--|
  |1|Prefix|`zm`|Identifies and groups children created by this project, for interfaces that do not expose tags. `z` will sort after most manually-created images and snapshots. `m` stands for "managed".|
  |2|Parent name or identifier|`webserver`|Conveniently indicates the parent. Derived from the `Name` tag (if not blank), the logical name (if supported), or the physical identifier (as a last resort). Multiple children of the same parent will sort together, by creation date (see next row).|
  |3|Date/time|`20171231T1400`|Indicates when the child was created. The last digit of the minute is normalized to 0. The `-` and `:` separators are removed for brevity, and because AWS does not allow `:` in resource names. (The [`managed-date-time` tag](#tag-managed-date-time) preserves the separators.)|
  |4|Random string|`g3a8a`|Guarantees unique names. Five characters are chosen from a small set of unambiguous letters and numbers.|

* If parsing is ever necessary, keep in mind that the second part may contain internal hyphens.
* This project replaces characters forbidden by AWS with `X`.
* For some resource types, the description is also set to the name, in case interfaces expose only one or the other.

### Special Tags

* Special tags are added to the child:

  |Tag(s)|Purpose|
  |--|--|
  |`Name`|Supplements EC2 resource identifier. The key is renamed `managed-parent-name` when the value is passed from parent to child, because the child has a `Name` tag of its own. The code handles `Name` specially for both EC2 and RDS, in case AWS someday extends EC2-style tag semantics to RDS.|
  |`managed-parent-name`|The `Name` tag value from the parent. Not added if blank.|
  |`managed-parent-id`|The identifier of the parent instance or volume. AWS metadata captures this (for example, as `VolumeId`, for EC2 EBS volume snapshots), but the interface differs for each resource type.|
  |`managed-origin`|The operation (for example, `snapshot`) that created the child. Identifies resources created by this project. Also distinguishes special cases, such as whether an EC2 instance was or was not rebooted before an image was created.|
  |<a name="tag-managed-date-time">`managed-date-time`</a>|Groups resources created during the same 10-minute interval. The last digit of the minute is normalized to 0. AWS metadata captures the _exact_ time, and the interface differs for each resource type.|

* Tags other than operation-enabling tags, schedule tags, and the `Name` tag, are copied from parent to child. (The deletion tag, `managed-delete`, would not make sense on instances and volumes, but if it is present, it is not copied to images and snapshots.)

## Operation Combinations

Multiple _non-simultaneous_ operations on the same resource are allowed.

### Supported Combinations

If two or more operations on the same resource are scheduled for the same 10-minute interval, the function combines them, where possible:

|Resource|Simultaneous Operations|Effect|
|--|--|--|
|EC2 instance|Create Image + Reboot|Reboot then Create Image|
|EC2 or RDS instance|Stop + Reboot|Stop|
|RDS instance|Stop + Create Snapshot|Create Snapshot then Stop|

The Create Image + Reboot combination for EC2 instances is useful. For example, you could take hourly backups but reboot only in conjunction with the midnight backup. The midnight backup would be guaranteed to be coherent for all files, but you could safely retrieve static files as of any given hour, from the other backups. To set up this example:

|Tag|Value|
|--|--|
|`managed-image`||
|`managed-image-periodic`|`d=*,H=*,M=59`|
|`managed-reboot`||
|`managed-reboot-periodic`|`d=*,H=23,M=59`|
  
23:59, which for the purposes of this project represents the last 10-minute interval of the day, is the unambiguous way to express _almost the end of some designated day_, on any system. 00:00 and 24:00 could refer to the start or the end of the designated day, and not all systems accept 24:00, in any case. Remember that all times are UTC; adjust for night-time in your time zone!

### Unsupported Combinations

Resources tagged for unsupported combinations of operations are logged (with message `OPS_UNSUPPORTED`) and skipped.

|Bad Combination|Reason|Example|
|--|--|--|
|Mutually exclusive operations|The operations conflict with each other.|Start + Stop|
|Choice of operation depends on current state of instance|The state of the instance could change between the status query and the operation request.|Start + Reboot|
|Sequential or dependent operations|The logical order cannot always be inferred. Also, operations proceed asynchronously; one might not complete in time for another to begin. Note that Reboot then Create Image (EC2 instance) and Create Snapshot then Stop (RDS instance) are _single_ AWS operations.|Start + Create Image|

## Security Model

 * Prevent unauthorized changes to the AWS Lambda function by attaching the TagSchedOpsPerformLambdaFnProtect IAM policy to most entities with write privileges for:
     * AWS Lambda
     * CloudFormation Events
     * CloudFormation Logs
     * IAM (roles and/or policies)
 
 * Allow only a few trusted users to tag EC2 and RDS resources, because tags determine which resources are started, backed up, rebooted, and stopped.

 * Tag backups for deletion, but let a special user or entity actually delete them. To mark images and snapshots for (manual) deletion, add the `managed-delete` tag.
 
 * Do not allow the same entities that create backups to delete backups (or even to tag them for deletion).
 
 * Choose from a library of IAM policies:
 
   |Policy Name|Manage Enabling Tags|Manage One-Time Schedule Tags|Manage Repetitive Schedule Tags|Back Up|Manage Deletion Tag|Delete|
   |--|--|--|--|--|--|--|
   |_Scope &rarr;_|_Instances, Volumes_|_Instances, Volumes_|_Instances, Volumes_|_Instances, Volumes_|_Images, Snapshots_|_Images, Snapshots_|
   |TagSchedOpsAdminister|Allow|Allow|Allow|No effect|Deny|Deny|
   |TagSchedOpsTagScheduleOnce|Deny [<sup>i</sup>](#policy-footnote-1)|Allow [<sup>ii</sup>](#policy-footnote-2)|Deny|No effect|Deny|Deny|
   |TagSchedOpsTagSchedulePeriodic|Deny [<sup>i</sup>](#policy-footnote-1)|No effect|Allow [<sup>ii</sup>](#policy-footnote-2)|No Effect|Deny|Deny|
   |TagSchedOpsTagForDeletion|Deny|Deny|Deny|Deny|Allow|Deny|
   |TagSchedOpsBackupDelete|Deny|Deny|Deny|Deny|Deny|Allow|
   |TagSchedOpsNoTag|Deny|Deny|Deny|No effect|Deny|Deny|
   
   Footnotes:
   
     1. <a name="policy-footnote-1"></a>For RDS, No Effect.
     2. <a name="policy-footnote-2"></a>Enabling tag required. For example, a user could only add `managed-image-once` to an EC2 instance already tagged with `managed-image`.
      
   These policies cover all regions. If you use regions to differentiate production and non-production resources, copy the policies and adapt them.

   Because Deny always takes precendence in IAM, some policy combinations conflict.

   A known shortcoming is that, in some cases, you cannot add, change or delete more than one tag in the same operation.
 
 * Although the TagSchedOpsAdminister and TagSchedOpsTag policies authorize tagging via the AWS API, users who are not AWS administrators may also want:
 
     * [AmazonEC2ReadOnlyAccess](https://console.aws.amazon.com/iam/home#policies/arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess), to use the EC2 Console
     * [AmazonRDSReadOnlyAccess](https://console.aws.amazon.com/iam/home#policies/arn:aws:iam::aws:policy/AmazonRDSReadOnlyAccess), to use the RDS Console

 * You may have to [decode authorization errors](http://docs.aws.amazon.com/cli/latest/reference/sts/decode-authorization-message.html). The TagSchedOpsAdminister and TagSchedOpsTag policies grant the necessary privilege.
 
 * Note these AWS technical limitations/oversights:
 
    * An entity that can create an image of an EC2 instance can force a reboot by omitting the `NoReboot` option. (Explicitly denying the reboot privilege does not help.) The unavoidable pairing of a harmless privilege, taking a backup, with a risky one, rebooting, is unfortunate.

    * Tags are ignored when deleting EC2 images and snapshots. Limit EC2 image and snapshot deletion privileges -- even Ec2TagSchedOpsDelete -- to highly-trusted entities.

    * In RDS, an entity that can add specific tags can add _any other_ tags in the same request. Limit RDS tagging privileges -- even the provided policies -- to highly-trusted users.

## Advanced Installation

### Multi-Region Configuration

If you intend to install TagSchedOps in multiple regions,

 * Set the StackSetsOrMultiRegion parameter to Yes.
 
 * Create S3 buckets in all [regions](http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region) where you intend to install TagSchedOps. The bucket names must have the same prefix, followed by a hyphen (`-`) and a suffix for the region. Set the LambdaCodeS3Bucket parameter to the shared prefix. For example, if you create `my-bucket-us-east-1` and `my-bucket-us-west-2`, set LambdaCodeS3Bucket to `my-bucket`. The region in which each bucket is created _must_ match the suffix in the bucket name.
 
 * Upload [`aws_tag_sched_ops_perform.py.zip`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws_tag_sched_ops_perform.py.zip) to each bucket. The need for copies in multiple regions is an AWS Lambda limitation.
 
 * Leave the TagSchedOpsPerformCodeS3VersionID parameter blank, because the value would differ in every region. Only the latest version of the AWS Lambda function source code file in each region's S3 bucket can be used.
 
 * Always set the MainRegion parameter to the same value. This prevents the creation of duplicate sets of user policies. (Those policies are not region-specific.)

### Multi-Account Configuration

If you intend to install TagSchedOps in multiple AWS accounts,

 * Create a bucket policy for each bucket, allowing `"s3:GetObject"` and `"s3:GetObjectVersion"` from each AWS account number. Using S3 Access Control Lists (ACLs), let alone public access, is discouraged.

### Manual Installation

Manual installation is adequate if the number of installations is small, but keeping more than one installation up-to-date could be difficult.

 * Repeat the [Quick Start](#quick-start) installation steps in each target region and/or target AWS account.

### CloudFormation Stack*Set* Installation

1. If TagSchedOps has been installed manually in any region, in any of your AWS accounts -- for example, based on the Quick Start instructions -- delete all existing TagSchedOps CloudFormation stacks.

2. Follow the [multi-*region* rules](#multi-region-configuration), if applicable.

3. Follow the [multi-*account* rules](#multi-account-configuration), if applicable.

4. If [StackSets](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-concepts.html) has never been used, create [AWSCloudFormationStackSet*Admin*istrationRole](https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetAdministrationRole.yml). Do this one time, in your main (multi-account scenario) or only (single-account scenario) AWS account. There is no need to create AWSCloudFormationStackSet*Exec*utionRole anywhere, using Amazon's template; instead, see the next step.

5. In every target AWS account, create [`cloudformation/tag-sched-ops-install.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops-install.yaml). Set:

|Item|Value|
|--|--|
|Stack name|`TagSchedOpsPreInstall`|
|AdministratorAccountId|AWS account number of main account (from step 4); does *not* update a pre-existing AWSCloudFormationStackSet*Exec*utionRole|
|AWSCloudFormationStackSet*Exec*utionRoleStatus|_Choose carefully!_|
|LambdaCodeS3Bucket|_Name of AWS Lambda function source code bucket (shared prefix, in a multi-region scenario)_|

6. (Back) in the AWS account with the AWSCloudFormationStackSet*Admin*istrationRole, go to the [StackSets Console](https://console.aws.amazon.com/cloudformation/stacksets/home#/stacksets).

7. Click Create StackSet, then select "Upload a template to Amazon S3", then click Browse and select your locally downloaded copy of [`cloudformation/aws_tag_sched_ops.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

|Item|Value|
|--|--|
|StackSet name|`TagSchedOps`|
|LambdaCodeS3Bucket|_From Step 5_|
|MainRegion|_Must be a target region in every target AWS account_|
|StackSetsOrMultiRegion|Yes|
|TagSchedOpsPerformCodeS3VersionID|_In a multi-region scenario, leave blank_|

8. On the next page, specify the target AWS accounts, typically by entering account numbers below "Deploy stacks in accounts". Then, move the target region(s) from "Available regions" to "Deployment order". It is a good idea to put the main region (from Step 7) first.

## Software Updates

New versions of the AWS Lambda function source code and the CloudFormation template will be released from time to time.

### CloudFormation Stack Update

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console) as a privileged user.

2. Go to the [S3 Console](https://console.aws.amazon.com/s3/home). Click the name of the bucket where you keep CloudFormation templates and their dependencies. Open the Properties tab. If Versioning is disabled, click anywhere inside the box, select "Enable versioning", and click Save.

3. Open the Overview tab. Upload the latest version of 
[`aws_tag_sched_ops_perform.py.zip`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws_tag_sched_ops_perform.py.zip) to S3.

4. Click the checkbox to the left of the newly-uploaded file. In the window that pops up, look below the Download button and reselect "Latest version". In the Overview section of the pop-up window, find the Link and copy the text _after_ `versionId=`. (The Version ID will not appear unless you expressly select "Latest version".)

   _Security Tip:_ Download the file from S3 and verify it. (In some cases, you can simply compare the ETag reported by S3.) <br/>`md5sum aws_tag_sched_ops_perform.py.zip` should yield `63743f89e05b89b4f6eb14ca7eedecc1`

5. Go to [Stacks](https://console.aws.amazon.com/cloudformation/home#/stacks) in the CloudFormation Console. Click the checkbox to the left of `TagSchedOps` (you might have given the stack a different name). From the Actions pop-up menu next to the blue Create Stack button, select Create Change Set For Current Stack.

6. Click Choose File, immediately below "Upload a template to Amazon S3", and navigate to your locally downloaded copy of the latest version of [`cloudformation/aws_tag_sched_ops.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

   |Item|Value|
   |--|--|
   |Change set name|_Type a name of your choice_|
   |TagSchedOpsPerformCodeS3VersionID|_Paste the Version ID, from S3_|
   
   _A different S3 Version ID makes CloudFormation recognize new AWS Lambda function source code. Once you are familiar with the full update procedure, you may skip Steps 2-5 and leave TagSchedOpsPerformCodeS3VersionID as it was, when you are certain that only the CloudFormation template, not the function source code, is changing._
   
7. Click through the remaining steps. Finally, click "Create change set".

8. In the Changes section, check the Replacement column.

   If True is shown on any row, check the Logical ID.
   
   1. If the resource is for internal use, ignore it.
   
   2. If, however, it a user policy, such as TagSchedOpsAdminister, open another Web browser window, go to [Policies](https://console.aws.amazon.com/iam/home#/policies) in the IAM Console, click the name of the policy, open the "Attached entities" tab, and detach the policy from all entities. Keep notes!

9. Click Execute, below the top-right corner of the CloudFormation Console window.

10. Refresh until the stack's status shows `UPDATE_COMPLETE`, in green.

11. If you had to detach any IAM policies, return to the IAM Console and attach the replacement policies to the original entities.

12. If TagSchedOps is installed in multiple regions, repeat the update steps in each region. The S3 Version IDs will differ.

### CloudFormation Stack*Set* Update

Differences when updating a StackSet instead of an ordinary stack:

 * Click the radio button to the left of TagSchedOps, in the [list of StackSets](https://console.aws.amazon.com/cloudformation/stacksets/home#/stacksets). From the Actions pop-up menu next to the blue Create StackSet button, select "Manage stacks in StackSet". Then, select "Edit stacks". On the next page, select "Upload a template to Amazon S3" and upload the latest version of [`cloudformation/aws_tag_sched_ops.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml).
 
 * A single update covers all target regions and/or AWS target accounts.
 
 * The TagSchedOpsPerformCodeS3VersionID parameter must remain blank. So that CloudFormation will recognize new source code for the AWS Lambda function, rename `aws_tag_sched_ops_perform.py.zip` to `aws_tag_sched_ops_perform_20170924.py.zip` (substitute current date) before uploading the file to the regional S3 bucket(s). Change the TagSchedOpsPerformCodeName parameter accordingly.

 * Change Sets are not supported. There is no preliminary feedback about the scope of changes.

## Future Work
     
 * Automated testing, consisting of a CloudFormation template to create sample AWS resources, and a program (perhaps another AWS Lambda function!) to check whether the intended operations were performed. An AWS Lambda function would also be ideal for testing security policies, while cycling through different IAM roles.
 
 * Archival policy syntax, and automatic application of `managed-delete` to expired backups. A correct archival policy is not strictly age-based. For example, you might preserve the last 30 daily backups, and beyond 30 days, the first backup of every month. Consider the flaw in the snapshot retention property of RDS database instances: the daily automatic snapshots created when that property is set can never be kept longer than 35 days.
 
 * Further modularization of [aws_tag_sched_ops_perform.py](/aws_tag_sched_ops_perform.py)
 
 * Additional AWS Lambda function, to automatically delete backups tagged `managed-delete`
 
 * Makefile
 
 * Tags and reference dictionary updates to support scheduled restoration of images and snapshots

## Dedication

This work is dedicated to [Ernie Salazar](https://github.com/ehsalazar), R&eacute;gis and Marianne Marcelin, and my wonderful colleagues of the past few years.

## Licensing

|Scope|License|Copy Included|
|--|--|--|
|Source code files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Source code within documentation files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Documentation files (including this readme file)|[GNU Free Documentation License (FDL) 1.3](http://www.gnu.org/licenses/fdl-1.3.html)|[zlicense-doc.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-doc.txt)|

Copyright 2017, Paul Marcelin

Contact: `marcelin` at `cmu.edu` (replace at with `@`)
