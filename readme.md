# Start, Reboot, Stop and Back Up AWS Resources with Tags

## RETIREMENT NOTICE

Thank you for your interest and support since 2017! This project was retired on September 24, 2022.

Please enjoy the successor,
[https://github.com/sqlxpert/lights-off-aws](https://github.com/sqlxpert/lights-off-aws)&nbsp;,
which features:

* New scheduled operations:
  * Hibernate EC2 instances
  * Start, stop, reboot and back up RDS database _clusters_ (Aurora)
  * Change a CloudFormation stack parameter to true or false, to create or delete expensive resources
 
* Parallelism and scalability, thanks to an SQS queue and a separate AWS Lambda function
  to "do" scheduled operations

* Much easier multi-region, multi-account deployment, with _service-managed_ CloudFormation
  StackSet deployment, now that there is an alternative to self-managed permissions

* Shorter and simpler Python code, IAM policies and CloudFormation templates

* Easier extensibility

* An object-oriented Python design

## Licensing

The project's licenses remain in force.

|Scope|License|Copy Included|
|--|--|--|
|Source code files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Source code within documentation files|[GNU General Public License (GPL) 3.0](http://www.gnu.org/licenses/gpl-3.0.html)|[zlicense-code.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-code.txt)|
|Documentation files (including this readme file)|[GNU Free Documentation License (FDL) 1.3](http://www.gnu.org/licenses/fdl-1.3.html)|[zlicense-doc.txt](https://github.com/sqlxpert/aws-tag-sched-ops/raw/master/zlicense-doc.txt)|

Copyright Paul Marcelin

Contact: `marcelin` at `cmu.edu` (replace at with `@`)
