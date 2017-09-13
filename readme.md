# Start, Reboot, Stop and Back Up AWS Resources with Tags

## Benefits

* **Save money** by stopping EC2 instances and RDS databases during off-hours
* **Enhance reliability** by taking frequent backups
* **Use tags** to schedule operations
* Secure tagging, and backup deletion, with Identity and Access Management (IAM) policies
* Install and update easily, with CloudFormation

## Quick Start

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console) as a privileged user.

   _Security Tip:_ To see which kinds of resources you'll be installing, look in the [CloudFormation template](/cloudformation/aws_tag_sched_ops.yaml). <br/>`grep 'Type: "AWS::' aws_tag_sched_ops.yaml | sort | uniq --count` works well.
   
2. Navigate to [Instances](https://console.aws.amazon.com/ec2/v2/home#Instances) in the EC2 Console. Right-click the Name or ID of an instance, select Instance Settings, and then select Add/Edit Tags. Add:

   |Key|Value|Note|
   |--|--|--|
   |`managed-image`||Leave value blank|
   |`managed-image-periodic`|`d=*,H:M=11:30`|Replace `11:30` with [current UTC time](https://www.timeanddate.com/worldclock/timezone/utc) + 15 minutes|

3. Navigate to the [S3 Console](https://console.aws.amazon.com/s3/home). Click the name of the bucket where you keep CloudFormation templates, or create the bucket, if necessary. Upload the compressed source code of the AWS Lambda function, [`aws_tag_sched_ops_perform.py.zip`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws_tag_sched_ops_perform.py.zip)

   _Security Tip:_ Remove public read and write access from the S3 bucket. Carefully limit write access.

   _Security Tip:_ Download the file from S3 and verify it. <br/>`md5sum aws_tag_sched_ops_perform.py.zip` should yield `3f061dc1025a224e1eb04bd74e993bda`

4. Navigate to the [CloudFormation Console](https://console.aws.amazon.com/cloudformation/home). Click Create Stack. Click Choose File, immediately below "Upload a template to Amazon S3", and navigate to your locally downloaded copy of [`cloudformation/aws_tag_sched_ops.yaml`](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

   |Item|Value|
   |--|--|
   |Stack name|`TagSchedOps`|
   |LambdaCodeS3Bucket|_Name of your S3 bucket_|
   
5. After 20 minutes, check [Images](https://console.aws.amazon.com/ec2/v2/home#Images:sort=desc:creationDate) in the EC2 Console.

6. Before deregistering (deleting) the sample image, note its ID, so that you can find and delete the associated [snapshots](https://console.aws.amazon.com/ec2/v2/home#Snapshots:sort=desc:startTime). Also untag the instance.

7. Navigate to [Users](https://console.aws.amazon.com/iam/home#/users) in the IAM Console. Click your regular (uprivileged) username. Click Add Permissions, then click "Attach existing policies directly". In the Search box, type `TagSchedOpsAdminister`. Add the two matching policies.
      
   _Security Tip_: Review EC2 and RDS tagging privileges for all entities.

8. Log out of the AWS Console. You can now manage the relevant tags without logging in as a privileged user.

## Warnings

 * Use other tools or procedures to confirm that intended AWS operations complete successfully. Verification is beyond the scope of this project.
 
 * Rebooting is usually necessary to make software updates take effect. Nevertheless, a system may stop working after it is rebooted. Weigh the benefits of software updates against the risks.
 
 * No backup is complete until it has been restored successfully. Test your backups!
 
 * Be aware of AWS charges, including but not limited to: the costs of running the AWS Lambda function, storing the output in CloudWatch Logs, and storing images and snapshots; the whole-hour cost when you stop an instance; the cost of storage for stopped instances, as well as detached volumes; and the costs that accumulate when AWS automatically starts an RDS instance that has been stopped for too many days.
 
 * Secure your own AWS environment. Test the AWS Lambda function and the IAM policies from end-to-end, to make sure that they work correctly and meet your expectations. To help improve this project, please submit [bug reports and feature requests](https://github.com/sqlxpert/aws-tag-sched-ops/issues), as well as proposed [code changes](https://github.com/sqlxpert/aws-tag-sched-ops/pulls).

## Operation Tags

* To enable an operation, add a tag from the table. Leave the value blank.

  |AWS Resource|Start|Create Image|Reboot then Create Image|Reboot|Create Snapshot|Create Snapshot then Stop|Stop|
  |--|--|--|--|--|--|--|--|
  |EC2 compute instance|`managed-start`|`managed-image`|`managed-reboot-image`|`managed-reboot`| | |`managed-stop`|
  |EC2 EBS disk volume| | | | |`managed-snapshot`| | |
  |RDS database instance|`managed-start`| | |`managed-reboot`|`managed-snapshot`|`managed-snapshot-stop`|`managed-stop`|

* Also add tags for [repetitive (`-periodic`)](#repetitive-schedules) and/or [one-time (`-once`)](#one-time-schedules) schedules. Prefix with the operation.
* If there are no corresponding schedule tags, an enabling tag will be ignored, and the operation will never occur.
* To temporarily suspend an operation, delete its enabling tag. You may leave its schedule tag(s) in place.
* Examples (for an EC2 or RDS instance):

  |Tags and Values|Success?|Comment|
  |--|--|--|
  |`managed-start` <br/>`managed-start-periodic`=`u=1,H=09,M=05`|Yes|Enabled and scheduled|
  |`managed-start`=`No` <br/>`managed-start-periodic`=`u=1,H=09,M=05`|Yes|Value of enabling tag is always ignored|
  |`managed-start` <br/>`managed-start-once`=`2017-12-31T09:05`|Yes||
  |`managed-start` <br/>`managed-start-periodic`=`u=1,H=09,M=05` <br/>`managed-start-once`=`2017-12-31T09:05`|Yes|Both repetitive and one-time schedule tags are allowed|
  |`managed-start`|No|No schedule tag|
  |`managed-start-once`=`2017-12-31`|No|No enabling tag (operation is suspended)|
  |`managed-start` <br/>`managed-start-once`|No|Blank schedule|
  |`managed-start` <br/>`managed-start-periodic`=`Monday`|No|Invalid schedule|
  |`managed-start` <br/>`managed-stop-periodic`=`u=1,H=09,M=05`|No|Enabling tag and schedule tag cover different operations|

## Scheduling
 
 * All times are UTC, on a 24-hour clock.
 * The AWS Lambda function runs once every 10 minutes. The last digit of the minute is always ignored. For example, an operation scheduled for `M=47` is expected to begin between 40 and 50 minutes after the hour.
 * Month and minute values must have two digits. Use a leading zero (for example, `03`) if a month or minute value is less than or equal to 9. (Weekday numbers have only one digit.)
 * Use a comma (`,`) _without spaces_ to separate components. The order of components within a tag value does not matter.
 * `T` separates day information from time; it is not a variable.
 * [Repetitive (`-periodic`)](#repetitive-schedules) and [one-time (`-once`)](#one-time-schedules) schedule tags are supported. Prefix with the operation.
 * If the corresponding [enabling tag](#operation-enabling-tags) is missing, schedule tags will be ignored, and the operation will never occur.

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
      * The `*` wildcard is allowed for day (every day of the month) and hour (every hour of the day).
      * For consistent one-day-a-month scheduling, avoid `d=29` through `d=31`.
      * Labels are from `strftime` and weekday numbers are [ISO 8601-standard](https://en.wikipedia.org/wiki/ISO_8601#Week_dates) (different from `cron`).

  * Examples:
  
    |Value of `-periodic` Schedule Tag|Demonstrates|Operation Begins|
    |--|--|--|
    |`d=28,H=14,M=25` _or_ `dTH:M=28T14:25`|Monthly event|Between 14:20 and 14:30 on the 28th day of every month.|
    |`d=1,d=8,d=15,d=22,H=03,H=19,M=01`|`cron`-style schedule|Between 03:00 and 03:10 and again between 19:00 and 19:10, on the 1st, 8th, 15th, and 22nd days of every month.|
    |`d=*,H=*,M=15,M=45,H:M=08:50`|Extra event in the day|Between 10 and 20 minutes after the hour and 40 to 50 minutes after the hour, every hour of every day, _and also_ every day between 08:50 and 09:00.|
    |`d=*,H=11,M=00,uTH:M=2T03:30,uTH:M=5T07:20`|Extra weekly events|Between 11:00 and 11:10 every day, _and also_ every Tuesday between 03:30 and 03:40 and every Friday between 07:20 and 7:30.|
    |`u=3,H=22,M=15,dTH:M=01T05:20`|Extra monthly event(s)|Between 22:10 and 22:20 every Wednesday, _and also_ on the first day of every month between 05:20 and 05:30.|
    
### One-Time Schedules
 
  * Tag suffix: `-once`

  * Values: one or more [ISO 8601 combined date and time strings](https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations), of the form `2017-03-21T22:40` (March 21, 2017, in this example)
      * Remember, the code runs once every 10 minutes and the _last digit of the minute is ignored_
      * Omit seconds and fractions of seconds
      * Omit time zone

## Operation Combinations

* Multiple _non-simultaneous_ operations on the same resource are allowed.
* If two or more operations on the same resource are scheduled for the same 10-minute interval, the function combines them, where possible:

  |Resource|Simultaneous Operations|Effect|
  |--|--|--|
  |EC2 instance|Stop + Reboot|Stop|
  |EC2 instance|Create Image + Reboot|Reboot then Create Image|
  |RDS instance|Stop + Reboot|Stop|
  |RDS instance|Stop + Create Snapshot|Create Snapshot then Stop|

* The Create Image + Reboot combination for EC2 instances is useful. For example, you could take hourly backups but reboot only in conjunction with the midnight backup. The midnight backup would be guaranteed to be coherent for all files, but you could safely retrieve static files as of any given hour, from the other backups. To set up this example:

  |Tag|Value|
  |--|--|
  |`managed-image`||
  |`managed-image-periodic`|`d=*,H=*,M=59`|
  |`managed-reboot`||
  |`managed-reboot-periodic`|`d=*,H=23,M=59`|
  
  (23:59, which for the purposes of this project represents the last 10-minute interval of the day, is the unambiguous way to express _almost the end of some designated day_, on any system. 00:00 and 24:00 could refer to the start or the end of the designated day, and not all systems accept 24:00, in any case. Remember that all times are UTC; adjust for night-time in your time zone!)

* Non-combinable operations result in no operation.

  |Bad Combination|Reason|Example|
  |--|--|--|
  |Mutually exclusive operations|The operations conflict with each other.|Start + Stop|
  |Choice of operation depends on current state of instance|The state of the instance could change between the status query and the operation request.|Start + Reboot|
  |Sequential or dependent operations|The logical order cannot always be inferred. Also, operations proceed asynchronously; one might not complete in time for another to begin. Note that Reboot then Create Image (EC2 instance) and Create Snapshot then Stop (RDS instance) are _single_ AWS operations.|Start + Create Image|
  
## "Child" Resources

Some operations create a child resource (image or snapshot) from a parent resource (instance or volume).
 
### Naming Conventions

* This project replaces characters forbidden by AWS with `X`.
* The name consists of these parts, separated by hyphens (`-`):

  |#|Part|Example|Purpose|
  |--|--|--|--|
  |1|Prefix|`zm`|Identifies and groups children created by this project, in interfaces that do not expose tags. `z` will sort after most manually-created images and snapshots. `m` stands for "managed".|
  |2|Parent name or identifier|`webserver`|Conveniently indicates the parent. Derived from the `Name` tag (if not blank), the logical name (if supported), or the physical identifier (as a last resort). Multiple children of the same parent will sort together, by creation date (see next row).|
  |3|Date/time|`20171231T1400`|Indicates when the child was created. The last digit of the minute is normalized to 0. The `-` and `:` separators are removed for brevity, and because AWS does not allow `:` in names, for some resource types. (The `managed-date-time` tag stores the original string, with separators intact.)|
  |4|Random string|`g3a8a`|Guarantees unique names. Five characters are chosen from a small set of unambiguous letters and numbers.|

* If parsing is ever necessary, keep in mind that the second part may contain internal hyphens.
* For some resource types, the description is also set to the name, in case interfaces expose only one or the other.

### Special Tags

* Tags other than operation-enabling tags, schedule tags, and the `Name` tag, are copied from parent to child. (The deletion tag, `managed-delete`, would not make sense on instances and volumes, but if it is present, it is not copied to images and snapshots.)

* Special tags are added to the child:

  |Tag(s)|Purpose|
  |--|--|
  |`Name`|Supplements EC2 resource identifiers. The key is renamed `managed-parent-name` when the value is passed from parent to child, because the child has a `Name` tag of its own. This project handles `Name` specially for both EC2 and RDS, in case EC2-style tag semantics are eventually extended to RDS.|
  |`managed-parent-name`|The `Name` tag value from the parent. Not added if blank.|
  |`managed-parent-id`|The identifier of the parent EC2 instance, EC2 EBS volume, or RDS instance. AWS metadata captures this (for example, as `VolumeId`, for EC2 EBS volume snapshots), but the interface differs for each resource type.|
  |`managed-origin`|The operation (for example, `snapshot`) that created the child. Identifies resources created by this project. Also distinguishes special cases, such as whether an EC2 instance was or was not rebooted before an image was created.|
  |`managed-date-time`|Groups resources created during the same 10-minute interval. AWS metadata captures the _exact_ time, and the interface differs for each resource type.|

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
 
   |Policy Name|Manage Operation-Enabling Tags|Manage One-Time Schedule Tags|Manage Repetitive Schedule Tags|Back Up|Manage Deletion Tag|Delete|
   |--|--|--|--|--|--|--|
   |_Scope &rarr;_|_Instances, Volumes_|_Instances, Volumes_|_Instances, Volumes_|_Instances, Volumes_|_Images, Snapshots_|_Images, Snapshots_|
   |TagSchedOpsAdminister|Allow|Allow|Allow|No effect|Allow [<sup>i</sup>](#policy-footnote-1)|Deny|
   |TagSchedOpsTagScheduleOnce|Deny [<sup>ii</sup>](#policy-footnote-2)|Allow [<sup>iii</sup>](#policy-footnote-3)|Deny|No effect|Deny|Deny|
   |TagSchedOpsTagSchedulePeriodic|Deny [<sup>ii</sup>](#policy-footnote-2)|No effect|Allow [<sup>iii</sup>](#policy-footnote-3)|No Effect|Deny|Deny|
   |TagSchedOpsTagForDeletion|Deny|Deny|Deny|Deny|Allow|Deny|
   |TagSchedOpsDelete|Deny|Deny|Deny|Deny|Deny|Allow|
   |TagSchedOpsNoTag|Deny|Deny|Deny|No effect|Deny|Deny|
   
   Footnotes:
   
     1. <a name="policy-footnote-1"></a>This is an exception, and it makes the policy suitable only for administrative users. Never use this policy in any kind of automation.
     2. <a name="policy-footnote-2"></a>For RDS, No Effect.
     2. <a name="policy-footnote-3"></a>Operation-enabling tag required. For example, a user could only add `managed-image-once` if an EC2 instance were already tagged with `managed-image`.
      
   Because Deny always takes precendence in IAM, some policy combinations conflict.
   
   A shortcoming of these policies is that, in some cases, you cannot add, change or delete more than one tag in the same operation.
   
 * Note AWS technical limitations/oversights:
 
    * An entity that can create an image of an EC2 instance can force a reboot by omitting the `NoReboot` option. (Explicitly denying the reboot privilege does not help.) The unavoidable pairing of a harmless privilege, taking a backup, with a risky one, rebooting, is unfortunate.

    * Tags are ignored when deleting EC2 images and snapshots. Limit EC2 image and snapshot deletion privileges -- even Ec2TagSchedOpsDelete -- to highly-trusted entities.

    * In RDS, an entity that can add specific tags can add _any other_ tags in the same request. Limit RDS tagging privileges -- even the provided policies -- to highly-trusted users.

## Future Work

 * Documentation updates:
 
     * Output format, and how to use CloudWatch Logs
     
     * `DEBUG` mode
     
     * CloudFormation change set instructions, for template and AWS Lambda function source code updates (includes S3 object versioning)
     
 * Automated testing, consisting of a CloudFormation template to create sample AWS resources, and a program (perhaps another AWS Lambda function!) to check whether the intended operations were performed. An AWS Lambda function would also be ideal for testing security policies, while cycling through different IAM roles.
 
 * Archival policy syntax, and automatic application of `managed-delete` to expired backups. A correct archival policy is not strictly age-based. For example, you might preserve the last 30 daily backups, and beyond 30 days, the first backup of every month. Consider the flaw in the snapshot retention property of RDS database instances: the daily automatic snapshots created when that property is set can never be kept longer than 35 days.
 
 * Simplification of [aws_tag_sched_ops.yaml](/cloudformation/aws_tag_sched_ops.yaml), including testing of CloudFormation's support for [YAML `&` anchors and `*` references](https://en.wikipedia.org/wiki/YAML#Advanced_components), and evaluation of general-purpose or CloudFormation-specific YAML preprocessors.
 
 * Further modularization of [aws_tag_sched_ops_perform.py](/aws_tag_sched_ops_perform.py)
 
 * Additional AWS Lambda function, to automatically delete backups tagged `managed-delete`
 
 * Makefile
 
 * Packaging for standalone execution outside AWS Lambda (`requirements.txt`, etc.), to encourage collaborative development
 
 * Tags and reference dictionary updates to support scheduled restoration of images and snapshots
 
 * Function to list AWS resources tagged for unsupported combinations of operations, in the usual compact, line-oriented format
 
 * Generalization of reference dictionaries to support more AWS services and resource types. (Which ones?)

## Dedication

This work is dedicated to [Ernie Salazar](https://github.com/ehsalazar), R&eacute;gis and Marianne Marcelin, and my wonderful colleagues of the past few years.

## Licensing

|Scope|License|Copy Included|
|--|--|--|
|Source code files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Source code within documentation files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Documentation files (including this readme file)|[GNU Free Documentation License (FDL) 1.3](http://www.gnu.org/licenses/fdl-1.3.html)|[zlicense-doc.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-doc.txt)|

Copyright 2017, Paul Marcelin
