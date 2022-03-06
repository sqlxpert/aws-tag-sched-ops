# Start, Reboot, Stop and Back Up AWS Resources with Tags

## Benefits

* **Save money** by stopping EC2 instances and RDS databases during off-hours
* Take back ups **more often**
* Schedule everything with **tags**
* Easily install in multiple regions and accounts

Jump to: [Installation](#quick-start) &bull; [Operation Tags](#enabling-operations) &bull; [Schedule Tags](#scheduling-operations) &bull; [Logging](#output) &bull; [Security](#security-model) &bull; [Multi-region/multi-account](#advanced-installation)

## Comparison with Lifecycle Manager

Since 2017, when this project started, Amazon has introduced [Data Lifecycle Manager](https://aws.amazon.com/blogs/aws/new-lifecycle-management-for-amazon-ebs-snapshots/) and [AWS Backup](https://aws.amazon.com/about-aws/whats-new/2019/01/introducing-aws-backup/). TagSchedOps has a few advantages of its own:

 * Cron-style tags on each EC2 instance, EBS volume or RDS database show when it will be backed up. You don't have to look up a backup schedule in a different AWS service.
 * You can take backups as many times a day as you like.
 * You can schedule EC2 instance and RDS database stops, starts, reboots and backups with the same tool.
 * You can also schedule one-time operations, and you can do it without changing your regular schedules.

## Quick Start

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console).

2. Go to the [list of EC2 instances](https://console.aws.amazon.com/ec2/v2/home#Instances). Add the following tags to an instance:

  |Key|Value|Note|
  |--|--|--|
  |<kbd>managed-image</kbd>||Leave blank|
  |<kbd>managed-image-periodic</kbd>|<kbd>d=\*&nbsp;H:M=11:30</kbd>|Replace 11:30 with [current UTC time](https://www.timeanddate.com/worldclock/timezone/utc) + 20 minutes|

3. Go to the [S3 Console](https://console.aws.amazon.com/s3/home). Create a bucket for CloudFormation templates and Lambda ZIP files. It must be in the region where you want to install TagSchedOps and you must put a hyphen and the region at the end of the bucket name (for example, <kbd>my-bucket-us-east-1</kbd>). Upload the Lambda ZIP file, [<samp>aws-lambda/aws_tag_sched_ops.py.zip</samp>](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws-lambda/aws_tag_sched_ops.py.zip) and the all of the CloudFormation templates in [<samp>cloudformation/</samp>](https://github.com/sqlxpert/aws-tag-sched-ops/master/cloudformation)

  _Security Tip:_ [Block public access](https://docs.aws.amazon.com/AmazonS3/latest/dev/access-control-block-public-access.html#console-block-public-access-options) to the bucket, and limit write access

  _Security Tip:_ For the Lambda ZIP file, compare the <samp>Etag</samp> reported by S3 with the checksum in [<samp>aws-lambda/aws_tag_sched_ops.py.zip.md5.txt</samp>](aws-lambda/aws_tag_sched_ops.py.zip.md5.txt)

4. Go to the [CloudFormation Console](https://console.aws.amazon.com/cloudformation/home). Click <samp>Create Stack</samp>. Click <samp>Choose File</samp>, immediately below <samp>Upload a template to Amazon S3</samp>, and navigate to your local copy of [<samp>cloudformation/aws_tag_sched_ops.yaml</samp>](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

  |Section|Item|Value|
  |--|--|--|
  ||Stack name|<kbd>TagSchedOps</kbd>|
  |Basics|Main region|Current region|
  |Basics|Lambda code S3 bucket|Name of your S3 bucket|

  For all other parameters, keep the default values.

5. After 20 minutes, check the [list of images](https://console.aws.amazon.com/ec2/v2/home#Images:sort=desc:creationDate).

6. Before deregistering (deleting) the sample image, note its ID, so that you can delete the associated [EBS snapshots](https://console.aws.amazon.com/ec2/v2/home#Snapshots:sort=desc:startTime). Also untag the instance.

7. Go to the [list of IAM users](https://console.aws.amazon.com/iam/home#/users). Click your regular, uprivileged username. Click <samp>Add permissions</samp> and then <samp>Attach existing policies directly</samp>. In the <samp>Search</samp> box, type <kbd>TagSchedOpsAdminister</kbd>. Add the two matching policies.

  _Security Tip_: Review all users' EC2 and RDS tagging privileges!

8. Log out of the AWS Console. You can now manage relevant tags, view logs, and decode errors, without logging in as a privileged user.

## Warnings

* Test your backups! Can they be restored successfully?

* Check that your backups have completed successfully -- or broaden your retention policy to select replacements for missing backups.

* Weigh the benefits of rebooting against the risks. Rebooting is sometimes necessary for a coherent backup, but a system may stop working afterward.

* Be aware of AWS charges, including but not limited to: the costs of running the AWS Lambda function, storing CloudWatch logs, and storing images and snapshots; the whole-hour cost when you stop an RDS, EC2 Windows, or EC2 commercial Linux instance (but [other EC2 instances have a 1-minute minimum charge](https://aws.amazon.com/blogs/aws/new-per-second-billing-for-ec2-instances-and-ebs-volumes/)); the ongoing cost of storage for stopped instances; and costs that resume when AWS automatically starts an RDS instance that has been stopped for too many days.

* Test the provided AWS Lambda functions and IAM policies in your own AWS environment. To help improve TagSchedOps, please submit [bug reports and feature requests](https://github.com/sqlxpert/aws-tag-sched-ops/issues), as well as [proposed changes](https://github.com/sqlxpert/aws-tag-sched-ops/pulls).

## Enabling Operations

* To enable an operation, add a tag from the table. Leave the tag value blank.

  | |Start|Create Image|Reboot then Create Image|Reboot then Fail Over|Reboot|Create Snapshot|Create Snapshot then Stop|Stop|
  |--|--|--|--|--|--|--|--|--|
  |_Enabling&nbsp;Tag_&nbsp;&rarr;|<kbd>managed-start</kbd>|<kbd>managed-image</kbd>|<kbd>managed-reboot-image</kbd>|<kbd>managed-reboot-failover</kbd>|<kbd>managed-reboot</kbd>|<kbd>managed-snapshot</kbd>|<kbd>managed-snapshot-stop</kbd>|<kbd>managed-stop</kbd>|
  |[EC2&nbsp;instance](https://console.aws.amazon.com/ec2/v2/home#Instances)|&check;|&check;|&check;||&check;|||&check;|
  |[EBS&nbsp;volume](https://console.aws.amazon.com/ec2/v2/home#Volumes)||||||&check;|||
  |[RDS&nbsp;instance](https://console.aws.amazon.com/rds/home#dbinstances:)|&check;|||&check;|&check;|&check;|&check;|&check;|

* Also add tags for [repetitive (<kbd>-periodic</kbd>)](#repetitive-schedules) and/or [one-time (<kbd>-once</kbd>)](#one-time-schedules) schedules. Prefix with the operation.
* If there are no corresponding schedule tags, an enabling tag will be ignored, and the operation will never occur.
* To temporarily suspend an operation, delete its enabling tag. You may leave its schedule tag(s) in place.
* Examples (for an EBS volume or and RDS instance):

  |Set of tags|Operation occurs?|Comment|
  |--|--|--|
  |<samp>managed&#x2011;snapshot</samp>:&nbsp;&empty; <br/><samp>managed&#x2011;snapshot&#x2011;periodic</samp>:&nbsp;<samp>d=01&nbsp;H=09&nbsp;M=05</samp>|Yes||
  |<samp>managed&#x2011;snapshot</samp>:&nbsp;&empty; <br/><samp>managed&#x2011;snapshot&#x2011;once</samp>:&nbsp;<samp>2017-12-31T09:05</samp>|Yes||
  |<samp>managed&#x2011;snapshot</samp>:&nbsp;&empty; <br/><samp>managed&#x2011;snapshot&#x2011;periodic</samp>:&nbsp;<samp>u=1&nbsp;H=09&nbsp;M=05</samp> <br/><samp>managed&#x2011;snapshot&#x2011;once</samp>:&nbsp;<samp>2017-12-31T09:05</samp>|Yes|Both repetitive and one-time schedules are allowed|
  |<samp>managed&#x2011;snapshot</samp>:&nbsp;<samp>No</samp> <br/><samp>managed&#x2011;snapshot&#x2011;periodic</samp>:&nbsp;<samp>u=1&nbsp;H=09&nbsp;M=05</samp>|Yes|The value of an enabling tag is ignored|
  |<samp>managed&#x2011;snapshot</samp>:&nbsp;&empty;|No|No schedule tag is present|
  |<samp>managed&#x2011;snapshot&#x2011;once</samp>:&nbsp;<samp>2017-12-31T09:05</samp>|No|No enabling tag is present (operation is suspended)|
  |<samp>managed&#x2011;snapshot</samp>:&nbsp;&empty; <br/><samp>managed&#x2011;snapshot&#x2011;once</samp>:&nbsp;&empty; |No|Schedule is invalid (blank)|
  |<samp>managed&#x2011;snapshot</samp>:&nbsp;&empty; <br/><samp>managed&#x2011;snapshot&#x2011;periodic</samp>:&nbsp;<samp>Monday</samp>|No|Schedule is invalid|
  |<samp>managed&#x2011;snapshot</samp>:&nbsp;&empty; <br/><samp>managed&#x2011;stop&#x2011;periodic</samp>:&nbsp;<samp>u=1&nbsp;H=09&nbsp;M=05</samp>|No|The enabling and schedule tags are for different operations|

  Each tag is shown in <var>key</var>:&nbsp;<var>value</var> form. &empty; means that the value is blank.

## Scheduling Operations

 * All times are UTC, on a 24-hour clock.
 * The TagSchedOpsPerform AWS Lambda function runs once every 10 minutes. It ignores the last digit of the minute. For example, <kbd>M=47</kbd> means _one time, between 40 and 50 minutes after the hour_.
 * Month and minute values must have two digits. Use a leading zero if necessary. (Weekday numbers have only one digit.)
 * Separate schedule components with a comma (<kbd>,</kbd>) or a space (<kbd>&nbsp;</kbd>). (RDS does not allow commas in tag values.) The order of components within a tag value does not matter.
 * <kbd>T</kbd> separates date from time; it is invariable.
 * [Repetitive (<kbd>-periodic</kbd>)](#repetitive-schedules) and [one-time (<kbd>-once</kbd>)](#one-time-schedules) schedule tags are supported. Prefix with the operation.
 * If the corresponding [enabling tag](#enabling-operations) is missing, schedule tags will be ignored, and the operation will never occur.

### Repetitive Schedules

* Tag suffix: <kbd>-periodic</kbd>

* Values: one or more components:

  |Name|Minimum|Maximum|Wildcard|Combines With|
  |--|--|--|--|--|
  |Day of month|<kbd>d=01</kbd>|<kbd>d=31</kbd>|<kbd>d=\*</kbd>|<kbd>H</kbd> and <kbd>M</kbd>, or <kbd>H:M</kbd>|
  |Weekday|<kbd>u=1</kbd> (Monday)|<kbd>u=7</kbd> (Sunday)||<kbd>H</kbd> and <kbd>M</kbd>, or <kbd>H:M</kbd>|
  |Hour|<kbd>H=00</kbd>|<kbd>H=23</kbd>|<kbd>H=\*</kbd>|<kbd>d</kbd> or <kbd>u</kbd>, and <kbd>M</kbd>|
  |Minute|<kbd>M=00</kbd>|<kbd>M=59</kbd>||<kbd>d</kbd> or <kbd>u</kbd>, and <kbd>H</kbd>|
  |Hour and minute|<kbd>H:M=00:00</kbd>|<kbd>H:M=23:59</kbd>||<kbd>d</kbd> or <kbd>u</kbd>|
  |Day of month, hour and minute|<kbd>dTH:M=01T00:00</kbd>|<kbd>dTH:M=31T23:59</kbd>|||
  |Weekday, hour and minute|<kbd>uTH:M=1T00:00</kbd>|<kbd>uTH:M=7T23:59</kbd>|||

  * Day, hour and minute must _all_ be specified in the tag value.
  * To specify multiple values, repeat a component. For example, <kbd>d=01&nbsp;d=11&nbsp;d=21</kbd> means _the 1st, 11th and 21st days of the month_.
  * Wildcards: <kbd>d=\*</kbd> means _every day of the month_ and <kbd>h=\*</kbd>, _every hour of the day_.
  * For consistent one-day-a-month scheduling, avoid <kbd>d=29</kbd> through <kbd>d=31</kbd>.
  * The letters match [<code>strftime</code>](http://manpages.ubuntu.com/manpages/xenial/man3/strftime.3.html) and the weekday numbers are [ISO 8601-standard](https://en.wikipedia.org/wiki/ISO_8601#Week_dates) (differs from cron).

* Examples:

  |Value of Repetitive Schedule Tag|Demonstrates|Timing|
  |--|--|--|
  |<samp>d=\*&nbsp;H:M=14:25</samp>|Once-a-day event|Between 14:20 and 14:30, every day|
  |<samp>uTH:M=1T14:25</samp>|Once-a-week event|Between 14:20 and 14:30, every Monday.|
  |<samp>dTH:M=28T14:25</samp>|Once-a-month event|Between 14:20 and 14:30 on the 28th day of every month|
  |<samp>d=1&nbsp;d=8&nbsp;d=15&nbsp;d=22&nbsp;H=03&nbsp;H=19&nbsp;M=01</samp>|cron schedule|Between 03:00 and 03:10 and again between 19:00 and 19:10, on the 1st, 8th, 15th, and 22nd days of every month|
  |<samp>d=\*&nbsp;H=\*&nbsp;M=15&nbsp;M=45&nbsp;H:M=08:50</samp>|Extra daily event|Between 10 and 20 minutes after the hour and 40 to 50 minutes after the hour, every hour of every day, _and also_ every day between 08:50 and 09:00|
  |<samp>d=\*&nbsp;H=11&nbsp;M=00&nbsp;uTH:M=2T03:30&nbsp;uTH:M=5T07:20</samp>|Two extra weekly events|Between 11:00 and 11:10 every day, _and also_ every Tuesday between 03:30 and 03:40 and every Friday between 07:20 and 7:30|
  |<samp>u=3&nbsp;H=22&nbsp;M=15&nbsp;dTH:M=01T05:20</samp>|Extra monthly event|Between 22:10 and 22:20 every Wednesday, _and also_ on the first day of every month between 05:20 and 05:30|

### One-Time Schedules

* Tag suffix: <kbd>-once</kbd>

* Values: one or more [ISO 8601 combined date/time strings](https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations), of the form <kbd>2017-03-21T22:40</kbd> (March 21, 2017, in this example)
  * Remember, TagSchedOpsPerform runs once every 10 minutes and ignores the last digit of the minute.
  * Leave out seconds, microseconds, and timezone (always UTC).

## Output

* After logging in to the [AWS Web Console](https://signin.aws.amazon.com/console), go to the [TagSchedOpsPerform CloudWatch log group](https://console.aws.amazon.com/cloudwatch/home#logs:prefix=/aws/lambda/TagSchedOps-TagSchedOpsPerformLambdaFn-). If you gave the CloudFormation stack a name other than <samp>TagSchedOps</samp>, check the [log groups for _all_ AWS Lambda functions](https://console.aws.amazon.com/cloudwatch/home#logs:prefix=/aws/lambda/) instead.

* Sample output:

  |<samp>initiated</samp>|<samp>rsrc_id</samp>|<samp>op</samp>|<samp>child_rsrc_type</samp>|<samp>child</samp>|<samp>child_op</samp>|<samp>note</samp>|
  |--|--|--|--|--|--|--|
  |<samp>9</samp>||||||<samp>2017&#x2011;09&#x2011;12T20:40</samp>|
  |<samp>1</samp>|<samp>i&#x2011;08abefc70375d36e8</samp>|<samp>reboot&#x2011;image</samp>|<samp>Image</samp>|<samp>zm-my-server-20170912T2040-83xx7</samp>|||
  |<samp>1</samp>|<samp>i&#x2011;08abefc70375d36e8</samp>|<samp>reboot&#x2011;image</samp>|<samp>Image</samp>|<samp>ami&#x2011;bc9fcbc6</samp>|<samp>tag</samp>||
  |<samp>1</samp>|<samp>i&#x2011;04d2c0140da5bb13e</samp>|<samp>start</samp>|||||
  |<samp>0</samp>|<samp>i&#x2011;09cdea279388d35a2</samp>|<samp>start,stop</samp>||||<samp>OPS_UNSUPPORTED</samp>|
  |<samp>0</samp>|<samp>my-database</samp>|<samp>reboot&#x2011;failover</samp>||||...<samp>ForceFailover cannot be specified</samp>...|

  _This run began September 12, 2017 between 20:40 and 20:50 UTC. An EC2 instance (ID prefix <samp>i-</samp>) is being rebooted and backed up, but the instance may not yet be ready, and the image may not yet be complete. The image is named <samp>zm-my-server-20170912T2040-83xx7</samp>, its ID is <samp>ami-bc9fcbc6</samp>, and it has been tagged. A different EC2 instance is starting, but may not yet be ready. A third EC2 instance is tagged for simultaneous start and stop, an impossible combination. An RDS database instance (no <samp>i-</samp> or <samp>vol-</samp> ID prefix) could not be rebooted with fail-over. (The full error message goes on to explain that it is not multi-zone.)_

* There is a header line, an information line, and one line for each operation.

* Values are tab-separated (but the CloudWatch Logs Console collapses multiple tabs).

* Columns and standard values:

  |<samp>initiated</samp>|<samp>rsrc_id</samp>|<samp>op</samp>|<samp>child_rsrc_type</samp>|<samp>child</samp>|<samp>child_op</samp>|<samp>note</samp>|
  |--|--|--|--|--|--|--|
  |Operation initiated?|Resource ID|Operation|Child type|Pointer to child|Child operation|Message|
  |<samp>0</samp>&nbsp;No <br/><samp>1</samp>&nbsp;Yes <br/><samp>9</samp>&nbsp;_Info.&nbsp;only_|<samp>i-</samp>&nbsp;EC2&nbsp;instance&nbsp;ID <br/><samp>vol-</samp>&nbsp;EBS&nbsp;volume&nbsp;ID <br/>RDS&nbsp;instance&nbsp;name|_See_ [_table_](#enabling-operations)|<samp>Image</samp> <br/><samp>Snapshot</samp> <br/><samp>DBSnapshot</samp>|_Name, ID, or ARN, as available_|<samp>tag</samp>||

* Although the TagSchedOpsAdminister and TagSchedOpsTagSchedule policies authorize read-only access to the logs via the AWS API, and seem to be sufficient for using the links provided above, users who are not AWS administrators may also want [additional CloudWatch privileges](http://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/iam-identity-based-access-control-cwl.html#console-permissions-cwl).

### Debugging Mode

If the <code>DEBUG</code> environment variable is set, TagSchedOpsPerform outputs internal reference data, including the regular expressions used to match schedule tags.

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console) as a privileged user. AWS Lambda treats changes to environment variables like changes to code.

2. Click on the [TagSchedOpsPerform AWS Lambda function](https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions?f0=a3c%3D%3AVGFnU2NoZWRPcHNQZXJmb3JtTGFtYmRhRm4%3D).

3. Scroll down. In the <samp>Environment variables</samp> section, type <kbd>DEBUG</kbd> in the first empty <samp>Key</samp> box. Leave the <samp>Value</samp> blank.

4. <a name="debug-step-4"></a>Scroll back to the top and click <samp>Save</samp>.

5. After 10 minutes, find debugging information in [CloudWatch Logs](#output).

6. Turn off debugging mode right away, because the extra information is long. Scroll down, click <samp>Remove</samp>, to the far right of <samp>DEBUG</samp>, scroll back up, and click <samp>Save</samp>.

## On/Off Switch

* The TagSchedOpsAdminister policies authorize turning TagSchedOpsPerform on or off completely.

* After logging in to the [AWS Web Console](https://signin.aws.amazon.com/console), go to [CloudWatch event rules](https://console.aws.amazon.com/cloudwatch/home#rules:). Click the radio button to the left of <samp>TagSchedOpsPerform10MinEventRule</samp>, then select <samp>Enable</samp> or <samp>Disable</samp> from the <samp>Actions</samp> pop-up menu, next to the blue <samp>Create rule</samp> button.

* This switch is per-region and per-AWS-account.

* Missed operations will not occur when the function is turned back on; there is no queue.

## Child Resources

Some operations create a child resource (image or snapshot) from a parent resource (instance or volume).

### Naming

* The name of the child consists of these parts, separated by hyphens (<samp>-</samp>):

  |#|Part|Example|Purpose|
  |--|--|--|--|
  |1|Prefix|<samp>zm</samp>|Identifies and groups children created by TagSchedOps, for interfaces that do not expose tags. <samp>z</samp> will sort after most manually-created images and snapshots. <samp>m</samp> stands for "managed".|
  |2|Parent name or identifier|<samp>webserver</samp>|Conveniently indicates the parent. Derived from the <samp>Name</samp> tag, the logical name, or the physical identifier. Multiple children of the same parent will sort together, by creation date.|
  |3|Date/time|<samp>20171231T1400Z</samp>|Indicates when the child was created. Always includes the <samp>Z</samp> suffix, for UTC. The last digit of the minute is 0. The <samp>-</samp> and <samp>:</samp> separators are removed. (The [<samp>managed-date-time</samp> tag](#tag-managed-date-time) preserves them.)|
  |4|Random string|<samp>g3a8a</samp>|Guarantees unique names. Five characters are chosen from a small set of unambiguous letters and numbers.|

* If parsing is ever necessary, keep in mind that the second part may contain internal hyphens.
* Characters forbidden by AWS are replaced with <samp>X</samp>.
* For some resource types, the description is also set to the name, in case interfaces expose only one or the other.

### Special Tags

* Special tags are added to the child:

  |Tag(s)|Purpose|
  |--|--|
  |<samp>Name</samp>|Supplements EC2 resource identifier. The key is renamed <samp>managed-parent-name</samp> when the value is passed from parent to child, because the child has a <samp>Name</samp> tag of its own. The code handles <samp>Name</samp> specially for both EC2 and RDS, in case AWS someday extends EC2-style tag semantics to RDS.|
  |<samp>managed&#x2011;parent&#x2011;name</samp>|The <samp>Name</samp> tag value from the parent. May be blank.|
  |<samp>managed&#x2011;parent&#x2011;id</samp>|The identifier of the parent instance or volume. AWS stores this in metadata for some but not all resource types, and the retrieval key differs for each resource type.|
  |<samp>managed&#x2011;origin</samp>|The operation (for example, <samp>snapshot</samp>) that created the child. Identifies resources created by TagSchedOps. Also distinguishes special cases, such as whether an EC2 instance was rebooted before an image was created.|
  |<a name="tag-managed-date-time"><samp>managed-date-time</samp></a>|Groups resources created during the same 10-minute interval. The last digit of the minute 0, and <samp>Z</samp> is always appended, for UTC. AWS stores the _exact_ time (too specific for grouping) in metadata, and the retrieval key and the format differ for each resource type!|

* Tags other than operation-enabling tags, schedule tags, and the <samp>Name</samp> tag, are copied from parent to child. (The deletion tag, <samp>managed-delete</samp>, would not make sense on instances and volumes, but if it is present, it is not copied to images and snapshots.)

## Operation Combinations

Multiple _non-simultaneous_ operations on the same resource are allowed.

### Supported Combinations

If two or more operations on the same resource are scheduled for the same 10-minute interval, TagSchedOpsPerform tries to combine them:

|Resource|Simultaneous Operations|Effect|
|--|--|--|
|EC2 instance|Create Image + Reboot|Reboot then Create Image|
|EC2 or RDS instance|Stop + Reboot|Stop|
|RDS instance|Stop + Create Snapshot|Create Snapshot then Stop|

The Create Image + Reboot combination for EC2 instances is useful. For example, you could take hourly backups but reboot only in conjunction with the midnight backup. The midnight backup would be guaranteed to be coherent for all files, but you could safely retrieve static files as of any given hour, from the other backups. To set up this example:

|Tag|Value|
|--|--|
|<kbd>managed&#x2011;image</kbd>||
|<kbd>managed&#x2011;image&#x2011;periodic</kbd>|<kbd>d=\*&nbsp;H=\*&nbsp;M=59</kbd>|
|<kbd>managed&#x2011;reboot</kbd>||
|<kbd>managed&#x2011;reboot&#x2011;periodic</kbd>|<kbd>d=\*&nbsp;H=23&nbsp;M=59</kbd>|

23:59, which for the purposes of TagSchedOps represents the last 10-minute interval of the day, is the unambiguous way to express _almost the end of some designated day_, on any system. 00:00 and 24:00 could refer to the start or the end of the designated day, and not all systems accept 24:00, in any case. Remember that all times are UTC; adjust for midnight in your timezone!

### Unsupported Combinations

Resources tagged for unsupported combinations of operations are logged (with message <samp>OPS_UNSUPPORTED</samp>) and skipped.

|Bad Combination|Reason|Example|
|--|--|--|
|Mutually exclusive operations|The operations conflict.|Start and Stop|
|Choice of operation depends on current state of instance|The state of the instance could change between the status query and the operation request.|Start or Reboot|
|Sequential or dependent operations|The logical order cannot always be inferred. Also, operations proceed asynchronously; one might not complete in time for another to begin. Note that Reboot then Create Image (EC2 instance) and Create Snapshot then Stop (RDS instance) are _single_ AWS operations.|Start then Create Image|

## Security Model

 * Prevent unauthorized changes to the AWS Lambda functions by attaching the TagSchedOpsLambdaFnProtect policy to most IAM users and roles with write privileges for:
   * AWS Lambda
   * CloudFormation Events
   * CloudFormation Logs
   * IAM (roles and/or policies)

 * Allow only a few trusted users to tag EC2 and RDS resources, because tags determine which resources are started, backed up, rebooted, and stopped, and when.

 * Tag images and snapshots for deletion, but let a separate IAM user or role actually delete them. Add the <kbd>managed-delete</kbd> tag.

 * Do not let a non-administrative IAM user or role that can create backups delete backups (or even tag them for deletion).

 * Choose from a library of IAM policies:

   |Policy Name|Manage Enabling Tags|Manage One-Time Schedule Tags|Manage Repetitive Schedule Tags|Back Up|Manage Deletion Tag|Delete|
   |--|--|--|--|--|--|--|
   |_Scope_&nbsp;&rarr;|_Instances, Volumes_|_Instances, Volumes_|_Instances, Volumes_|_Instances, Volumes_|_Images, Snapshots_|_Images, Snapshots_|
   |TagSchedOpsAdminister|Allow|Allow|Allow|No effect|Allow|Deny|
   |TagSchedOpsTagScheduleOnce|Deny|Allow [<sup>i</sup>](#policy-footnote-1)|Deny|No effect|Deny|Deny|
   |TagSchedOpsTagForDeletion|Deny|Deny|Deny|Deny|Allow|Deny|
   |TagSchedOpsBackupDelete|Deny|Deny|Deny|Deny|Deny|Allow|
   |TagSchedOpsNoTag|Deny|Deny|Deny|No effect|Deny|Deny|

   Note:

     1. <a name="policy-footnote-1"></a>Enabling tag required. For example, a user could add <kbd>managed-image-once</kbd> to an EC2 instance only if the <samp>managed-image</samp> tag were already present.

   Because <code>Deny</code> always takes precendence in IAM, some policy combinations conflict.

   In some cases, you must add, change or delete one tag at a time.

 * Although the TagSchedOpsAdminister and TagSchedOpsTag policies authorize tagging via the AWS API, users who are not AWS administrators may also want console access:

     * [AmazonEC2ReadOnlyAccess](https://console.aws.amazon.com/iam/home#policies/arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess)
     * [AmazonRDSReadOnlyAccess](https://console.aws.amazon.com/iam/home#policies/arn:aws:iam::aws:policy/AmazonRDSReadOnlyAccess)

 * You may have to [decode authorization errors](http://docs.aws.amazon.com/cli/latest/reference/sts/decode-authorization-message.html). The TagSchedOpsAdminister and TagSchedOpsTag policies grant the necessary privilege.

 * Note these AWS limitations:

    * Authority to create an EC2 instance image includes authority to reboot. (Explicitly denying the reboot privilege does not help.) A harmless privilege, taking a backup, is married with a risky one, rebooting.

    * Tags are ignored when deleting EC2 images and snapshots. Limit EC2 image and snapshot deletion privileges to highly-trusted IAM users and roles.

    * In RDS, an IAM user or role that can add specific tags can add _any other_ tags at the same time. The provided policies prevent this with <code>Deny</code> statements, which unfortunately block legitimate RDS database and/or snapshot tagging privileges, if you have granted any.

## Advanced Installation

Before starting a multi-region and/or multi-account installation, delete the ordinary TagSchedOps CloudFormation stack in all regions, in all AWS accounts.

### Multi-Region Configuration

If you intend to install TagSchedOps in multiple regions,

1. Create S3 buckets in all [regions](http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region) where you intend to install TagSchedOps. The bucket names must all share the same prefix, which will be followed by a region suffix (e.g. <kbd>-us-east-1</kbd>). The region in which each bucket is created _must_ match the suffix at the end of the bucket's name.

2. Upload [<samp>aws-lambda/aws_tag_sched_ops_perform.py.zip</samp>](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws-lambda/aws_tag_sched_ops_perform.py.zip) to each bucket. The need for copies in multiple regions is an AWS Lambda limitation.

3. Keep the following rules in mind when setting parameters, later:

   |Section|Parameter|Value|
   |--|--|--|
   |Basics|Main region|_Always use the same value, to prevent the creation of duplicate sets of user policies_|
   |Basics|Multi-region or StackSets?|Yes|
   |Basics|Lambda code S3 bucket|_Use the shared prefix; for example, if you created_ <samp>my-bucket-us-east-1</samp> _and_ <samp>my-bucket-us-west-2</samp> _, use_ <kbd>my-bucket</kbd>|
   |TagSchedOpsAge|S3 version ID|_Leave blank, because the value would differ in every region; only the latest version of the AWS Lambda function source code file in each region's S3 bucket can be used_|
   |TagSchedOpsPerform|S3 version ID|_Leave blank, as above_|

### Multi-Account Configuration

If you intend to install TagSchedOps in multiple AWS accounts,

1. In every target AWS account, create the [pre-installation stack](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops-install.yaml). Set:

   |Item|Value|
   |--|--|
   |Stack name|<kbd>TagSchedOpsInstall</kbd>|
   |AWSCloudFormationStackSet*Exec*utionRoleStatus|_Choose carefully!_|
   |AdministratorAccountId|AWS account number of main (or only) account; leave blank if AWSCloudFormationStackSet*Exec*utionRole existed before this stack was created|
   |LambdaCodeS3Bucket|Name of AWS Lambda function source code bucket (shared prefix, in a multi-region scenario)|

2. For the AWS Lambda function source code S3 bucket in *each region*, create a bucket policy allowing access by *every target AWS account*'s AWSCloudFormationStackSetExecutionRole (StackSet installation) or TagSchedOpsCloudFormation role (manual installation with ordinary CloudFormation). The full name of the TagSchedOpsCloudFormation role will vary; for every target AWS account, look up the random suffix in [IAM roles](https://console.aws.amazon.com/iam/home#/roles), or by selecting the TagSchedOpsInstall stack in [CloudFormation stacks](https://us-east-2.console.aws.amazon.com/cloudformation/home#/stacks) and drilling down to <samp>Resources</samp>. S3 bucket policy template:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": [
             "arn:aws:iam::TARGET_AWS_ACCOUNT_NUMBER_1:role/AWSCloudFormationStackSetExecutionRole",
             "arn:aws:iam::TARGET_AWS_ACCOUNT_NUMBER_1:role/TagSchedOpsInstall-TagSchedOpsCloudFormation-RANDOM_SUFFIX_1",

             "arn:aws:iam::TARGET_AWS_ACCOUNT_NUMBER_2:role/AWSCloudFormationStackSetExecutionRole",
             "arn:aws:iam::TARGET_AWS_ACCOUNT_NUMBER_2:role/TagSchedOpsInstall-TagSchedOpsCloudFormation-RANDOM_SUFFIX_2"

           ]
         },
         "Action": [
           "s3:GetObject",
           "s3:GetObjectVersion"
         ],
         "Resource": "arn:aws:s3:::BUCKET_NAME/*"
       }
     ]
   }
   ```

### CloudFormation Stack*Set* Installation

1. Follow the [multi-region steps](#multi-region-configuration), even for a multi-account, single-region scenario.

2. Follow the [multi-account steps](#multi-account-configuration). In a single-account, multi-region scenario, no S3 bucket policy is needed.

3. If [StackSets](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-concepts.html) has never been used, create [AWSCloudFormationStackSet*Admin*istrationRole](https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetAdministrationRole.yml). Do this one time, in your main (multi-account scenario) or only (single-account scenario) AWS account. There is no need to create AWSCloudFormationStackSet*Exec*utionRole using Amazon's template; the TagSchedOps*Install* stack provides it, when necessary.

4. In the AWS account with the AWSCloudFormationStackSet*Admin*istrationRole, go to the [StackSets Console](https://console.aws.amazon.com/cloudformation/stacksets/home#/stacksets).

5. Click <samp>Create StackSet</samp>, then select <samp>Upload a template to Amazon S3</samp>, then click <samp>Browse</samp> and select your local copy of [<samp>cloudformation/aws_tag_sched_ops.yaml</samp>](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

   |Section|Item|Value|
   |--|--|--|
   ||StackSet name|<kbd>TagSchedOps</kbd>|
   |Basics|Main region|_Must be a StackSet target region_|
   |Basics|Lambda code S3 bucket|_Use the shared prefix; for example, if you created_ <samp>my-bucket-us-east-1</samp> _, use use_ <kbd>my-bucket</kbd>|
   |Basics|Multi-region or StackSets?|Yes|
   |TagSchedOpsAge|S3 version ID|_For multi-region, leave blank_|
   |TagSchedOpsPerform|S3 version ID|_For multi-region, leave blank_|

6. On the next page, specify the target AWS accounts, typically by entering account numbers below <samp>Deploy stacks in accounts</samp>. Then, move the target region(s) from <samp>Available regions</samp> to <samp>Deployment order</samp>. It is a good idea to put the main region first.

### Manual Installation

Manual installation is adequate if the number of installations is small, but keeping more than one installation up-to-date could be difficult.

1. Follow the [multi-region steps](#multi-region-configuration), if applicable.

2. Follow the [multi-account steps](#multi-account-configuration), if applicable.

3. Follow the [Quick Start](#quick-start) installation steps in each target region and/or target AWS account. Set parameters based on the multi-region and/or multi-account rules.

    * In a multi-account scenario, select the TagSchedOpsCloudFormation IAM Role during this step; CloudFormation may not be able to create the stack without assuming this role.

      If the IAM user who will invoke CloudFormation is not an administrator, attach the following policies beforehand:

      |Policy|Source|
      |--|--|
      |[AmazonS3FullAccess](https://console.aws.amazon.com/iam/home?#/policies/arn:aws:iam::aws:policy/AmazonS3FullAccess)|AWS|
      |[AmazonSNSReadOnlyAccess](https://console.aws.amazon.com/iam/home?#/policies/arn:aws:iam::aws:policy/AmazonSNSReadOnlyAccess)|AWS|
      |[IAMReadOnlyAccess](https://console.aws.amazon.com/iam/home?#/policies/arn:aws:iam::aws:policy/IAMReadOnlyAccess)|AWS|
      |TagSchedOpsCloudFormationRolePass|TagSchedOpsInstall stack|
      |CloudFormationFullAccess|TagSchedOpsInstall stack|

      Detach these policies -- particularly AmazonS3FullAccess and CloudFormationFullAccess -- after the stack has been created. AWS does not publish the _minimum_ privileges needed to create a stack. Full S3 access is obviously risky, and full CloudFormation access allows a non-administrator to modify or delete _any_ stack with an IAM Role.

## Software Updates

New versions of AWS Lambda function source code and CloudFormation templates will be released from time to time.

### CloudFormation Stack Update

1. Log in to the [AWS Web Console](https://signin.aws.amazon.com/console) as a privileged user.

2. Go to the [S3 Console](https://console.aws.amazon.com/s3/home). Click the name of the bucket where you keep CloudFormation templates and their dependencies. Open the <samp>Properties</samp> tab. If Versioning is disabled, enable it now.

3. Return to the <samp>Overview</samp> tab. Upload the latest version of
[<samp>aws-lambda/aws_tag_sched_ops_perform.py.zip</samp>](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/aws-lambda/aws_tag_sched_ops_perform.py.zip) to S3.

4. Click the name of the newly-uploaded object. Near the top of the page, click to open the <samp>Latest version</samp> pop-up menu and then click to select the <samp>Latest version</samp>. Copy the <samp>Version ID</samp>. (It will not appear unless you actually select <samp>Latest version</samp> from the pop-up.)

   _Security Tip:_ Download the file from S3 and verify it, or compare the Etag reported by S3. <kbd>md5sum aws-lambda/aws_tag_sched_ops_perform.py.zip</kbd> should match [<samp>aws-lambda/aws_tag_sched_ops_perform.py.zip.md5.txt</samp>](aws-lambda/aws_tag_sched_ops_perform.py.zip.md5.txt)

5. Go to [CLoudFormation stacks](https://console.aws.amazon.com/cloudformation/home#/stacks). Click the checkbox to the left of <samp>TagSchedOps</samp> (you might have given the stack a different name). From the <samp>Actions</samp> pop-up menu next to the blue <samp>Create Stack</samp> button, select <samp>Create Change Set For Current Stack</samp>.

6. Click <samp>Choose File</samp>, immediately below <samp>Upload a template to Amazon S3</samp>, and navigate to your local copy of the latest version of [<samp>cloudformation/aws_tag_sched_ops.yaml</samp>](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml). On the next page, set:

   |Section|Item|Value|
   |--|--|--|
   ||<samp>Change set name</samp>|_Type a name of your choice_|
   |TagSchedOpsAdd|<samp>S3 version ID</samp>|_Paste the Version ID of <samp>age_backups.py.zip</samp>, from S3_|
   |TagSchedOpsPerform|<samp>S3 version ID</samp>|_Paste the Version ID of <samp>aws_tag_sched_ops_perform.py.zip</samp>, from S3_|

   _A different S3 Version ID makes CloudFormation recognize new source code. Once you are familiar with the full update procedure, you may skip Steps 2-5 and leave the Version IDs as they were, when you are certain that only the CloudFormation template, not the function source code, is changing._

7. Click through the remaining steps. Finally, click <samp>Create change set</samp>.

8. In the <samp>Changes</samp> section, check the <samp>Replacement</samp> column.

   If <samp>True</samp> is shown on any row, check the <samp>Logical ID</samp>.

   1. If the resource is for internal use, ignore it.

   2. If, however, it a user policy, such as TagSchedOpsAdminister, open another Web browser window, go to [IAM policies](https://console.aws.amazon.com/iam/home#/policies), click the name of the policy, open the <samp>Attached entities</samp> tab, and detach the policy from all entities. Keep notes!

9. Click <samp>Execute</samp>, below the top-right corner of the CloudFormation Console window.

10. Refresh until the stack's status shows <samp>UPDATE_COMPLETE</samp>, in green.

11. If you had to detach any IAM policies, attach the replacement policies to the original entities.

12. If TagSchedOps is installed in multiple regions, repeat the update steps in each region. The S3 Version IDs will differ.

### CloudFormation Stack*Set* Update

Differences when updating a StackSet instead of an ordinary stack:

 * Click the radio button to the left of TagSchedOps, in the [list of StackSets](https://console.aws.amazon.com/cloudformation/stacksets/home#/stacksets). From the <samp>Actions</samp> pop-up menu next to the blue <samp>Create StackSet</samp> button, select <samp>Manage stacks in StackSet</samp>. Then, select <samp>Edit stacks</samp>. On the next page, select <samp>Upload a template to Amazon S3</samp> and upload the latest version of [<samp>cloudformation/aws_tag_sched_ops.yaml</samp>](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/cloudformation/aws_tag_sched_ops.yaml).

 * A single update covers all target regions and/or AWS target accounts.

 * The S3 Version ID parameters must remain blank. So that CloudFormation will recognize new source code for the AWS Lambda functions, rename each ZIP file. (For example, change <samp>aws_tag_sched_ops_perform.py.zip</samp> to <samp>aws_tag_sched_ops_perform_20170924.py.zip</samp>.) Change the <samp>S3 object name</samp> parameters accordingly.

 * Change Sets are not supported. StackSets provides no preliminary feedback about the scope of changes.

## Future Work

 * Automated testing, consisting of a CloudFormation template to create sample AWS resources, and a program (perhaps another AWS Lambda function!) to check whether the intended operations were performed. An AWS Lambda function would also be ideal for testing security policies, while cycling through different IAM roles.

 * Additional AWS Lambda function, to automatically delete backups tagged <samp>managed-delete</samp>

 * Makefile

 * Tags and reference dictionary updates to support scheduled restoration of images and snapshots (for backup testing?)

## Dedication

This work is dedicated to [Ernie Salazar](https://github.com/ehsalazar), R&eacute;gis and Marianne Marcelin, and my wonderful colleagues of the past few years.

## Licensing

|Scope|License|Copy Included|
|--|--|--|
|Source code files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Source code within documentation files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Documentation files (including this readme file)|[GNU Free Documentation License (FDL) 1.3](http://www.gnu.org/licenses/fdl-1.3.html)|[zlicense-doc.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-doc.txt)|

Copyright 2022, Paul Marcelin

Contact: <kbd>marcelin</kbd> at <kbd>cmu.edu</kbd> (replace at with <kbd>@</kbd>)
