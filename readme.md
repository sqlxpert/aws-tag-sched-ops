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


## Scheduling
 
 * All times are UTC, on a 24-hour clock.
 * The function runs once every 10 minutes. The last digit of the minute is always ignored. For example, an operation scheduled for `M=47` is expected to begin between 40 and 50 minutes after the hour, depending on startup overhead.
 * Month and minute values must always have two digits. Use a leading zero (for example, `03`) if the value is less than 10.
 * Use a comma (`,`) _without any spaces_ to separate components. The order of components within a tag value does not matter.
 * `T` separates day information from time; it is not a variable.
 * Different tags are used for repeating (`-periodic`) and one-time (`-once`) schedules.

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
      * Labels are from `strftime` and weekday numbering follows the [ISO 8601 standard](https://en.wikipedia.org/wiki/ISO_8601#Week_dates) (different from `cron`).

  * Examples:
  
    |Value of `-periodic` Schedule Tag|Demonstrates|Operation Expected to Begin|
    |--|--|--|
    |`d=28,H=14,M=25` _or_ `dTH:M=28T14:25`|Monthly event|Between 14:20 and 14:30 on the 28th day of every month.|
    |`d=1,d=8,d=15,d=22,H=03,H=19,M=01`|`cron`-style schedule|Between 03:00 and 03:10 and again between 19:00 and 19:10, on the 1st, 8th, 15th, and 22nd days of every month.|
    |`d=*,H=*,M=15,M=45,H:M=08:50`|Extra event in the day|Between 10 and 20 minutes after the hour and 40 to 50 minutes after the hour, every hour of every day, _and also_ every day between 08:50 and 09:00.|
    |`d=*,H=11,M=00,uTH:M=2T03:30,uTH:M=5T07:20`|Extra weekly events|Between 11:00 and 11:10 every day, _and also_ every Tuesday between 03:30 and 03:40 and every Friday between 07:20 and 7:30.|
    |`u=3,H=22,M=15,dTH:M=01T05:20`|Extra monthly event(s)|Between 22:10 and 22:20 every Wednesday, _and also_ on the first day of every month between 05:20 and 05:30.|
    
### One-Time Schedules
 
  * Tag suffix: `-once`

  * Values: one or more [ISO 8601 combined date and time strings](https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations), of the form `2017-03-21T22:40`
      * Remember, the code runs once every 10 minutes and the _last digit of the minute is ignored_
      * Omit seconds and fractions of seconds
      * Omit time zone

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
