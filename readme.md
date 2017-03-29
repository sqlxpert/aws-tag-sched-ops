# Schedule Snapshots, Images and Reboot with Tags #

## Purpose ##

Create snapshots and images, and reboot, using simple, tag-based schedules

|AWS Resource|Supported Action|
|---|---|
|EC2 (compute) instance|Create image|
|EC2 (compute) instance|Reboot|
|EBS (disk) volume|Create snapshot|
|RDS (database) instance|Create snapshot|
|RDS (database) instance|Reboot|

## Security Model ##

### Constraints ###

 * Restricting **tagging privileges** is crucial, because tags determine what gets backed up and/or rebooted, and when.
 * It is not possible to restrict tagging privileges to particular kinds of EC2 resources, let alone to particular EC2 resources.
 * The right to _add_ tags to EC2 or RDS resources includes the right to _change_ the values of existing tags.
 * Although it is possible to restrict tagging privileges to RDS resources that already have particular tags, there _results_ of a tagging call are not checked.

 * Restricting **reboot privileges** is crucial. Reboots clear ephemeral data (such as cache) and may make services unavailable. A service might even fail to start after a reboot.
 * Denying EC2 instance reboot privileges does not prevent forcing a reboot as part of an image creation call.

 * Restricting RDS **database snapshot** privileges is crucial. An RDS snapshot might degrade database performance and block RDS instance modifications for a long period of time.

### Effects ###

 * Support for positive tags (e.g., "yes, reboot") as well as negative ones (e.g., "no, do not reboot") is a necessary compromise.
 * Where a positive and a negative tag conflict, the safer interpretation prevails.

 * Different IAM managed policies are provided for:
     * Ad-hoc tagging (`TagAddChange`). These policies confer the right to add and change tags, but deny the right to delete tags. Because `Deny` takes precedence over `Allow` in IAM, these policies have the side-effect of preventing users -- even administrators -- from deleting tags from any EC2 resource of any kind, from any RDS instance, and from any RDS snapshot, as applicable.
     * Baseline tagging (`TagAdmin`). These policies confer the right to add, change and delete tags.
 * Your organization's tagging controls might be different. The `Tag` policies are provided only as a starting point.
 
 * Ad-hoc tagging rights must never be combined with the right to modify the source code of the AWS Lambda function that creates snapshots and initiates reboots. The code serves as a security barrier. It is designed to respect baseline, negative tags that forbid reboot.

## Licenses ##

|Scope|License|
|---|---|
|Source code files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|
|Source code within documentation files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|
|Documentation files|[GNU Free Documentation License (FDL) 1.3](http://www.gnu.org/licenses/fdl-1.3.html)|

Paul Marcelin, 2017
