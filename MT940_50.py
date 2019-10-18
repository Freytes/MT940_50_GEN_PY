# -------------------------------------------------------------------------------
# Name:        Swift MT940/950 Generator
# Purpose:     Takes a specific csv file and converts it to
#              either an MT940 or MT950 swift message.
# Version:     1.2.0
# Author:      Thomas Edward Rudge
# Created:     25-10-2015
# Updated:     18-10-2019
# Copyright:   (c) Thomas Edward Rudge 2015
# Modified by: Christopher Freytes 2019
# Licence:     GPL
# -------------------------------------------------------------------------------
# Written for Python 3.8.6

import csv, os, datetime
from datetime import datetime


def gen_mt9(active_file=r"\DIR\sample.csv",
            msg_type='940',
            target_file=r'\DIR\MT940' + '.' + str(
                datetime.now().strftime('%Y_%m_'
                                        '%d_%H_'
                                        '%M_%S')) + '.fin',
            dtf='DDMMYYYY',
            # Basic Header Block
            appid='F',
            servid='21',
            session_no='0000',
            seqno='000000',
            # Application Header Block
            drctn='I',
            msg_prty='N',
            dlvt_mnty='',
            obs='',
            inp_time='0000',
            out_date='000000',
            out_time='0000',
            mir=True,
            # User Header Block
            f113=False,
            mur='MT940950GEN',
            chk=False):
    '''
    CSV --> MT940/50
    All arguments must be strings.
    ---------------------------------------------------------------
    active_file : The location of the csv file to be read.
    msg_type    : Either 940 or 950
    target_file : The location where the MT940/50 should be written
    ---------------------------------------------------------------
    # Optional Arguments
    dtf         : The format of the dates present in the csv file - YYYYMMDD
                                                                    DDMMYYYY (Default)
                                                                    MMDDYYYY
    {1: Basic Header Block ----------------------------------------
    appid       : Application ID - A = General Purpose Application
                                   F = Financial Application
                                   L = Logins
    servid      : Service ID - 01 = FIN/GPA
                               21 = ACK/NAK
    session_no  : Session Number
    seqno       : Sequence Number
    {2: Application Header Block ----------------------------------
    drctn       : Direction - I =Input (to swift)
                              O = Output (from swift)
    msg_prty    : Message Priority - S = System
                                     N = Normal
                                     U = Urgent)
    dlvt_mnty   : Delivery Monitoring Field - 1 = Non delivery warning
                  [Input Only]                2 = Delivery notification
                                              3 = Both (1 & 2)
    obs         : Obsolescence period - 003 = 15 minutes (When priority = U)
                  [Input Only]          020 = 100 minutes (When priority = N)
    inp_time    : Input Time of Sender - HHMM - [Output Only]
    out_time    : Output Time from Swift - HHMM - [Output Only]
    out_date    : Output Date from Swift - YYMMDD - [Output Only]
    mir         : Message Input Reference - If True MIR is autogenerated, all
                  [Output Only]             other values will be used as the MIR
    {3: User Header Block -----------------------------------------
    f113        : Banking Priority Code - nnnn
    mur         : Message User Reference
    {5: Trailer Block ---------------------------------------------
    chk         : The checksum for the message.

    File appending arguments
    ---------------------------------------------------------------
    w  write mode
    r  read mode
    a  append mode

    w+  create file if it doesn't exist and open it in write mode
    r+  open for reading and writing. Does not create file.
    a+  create file if it doesn't exist and open it in append mode
    '''
    if not os.path.isfile(active_file):
        return False

    with open(active_file, 'r+') as afile, open(target_file, 'w+') as zfile:
        # Keep track of the last lines details, so that we know when to close the statement or message.
        prev_line = {
            'account': '',
            'sendbic': '',
            'recvbic': '',
            'stmtno': '',
            'stmtpg': '',
            'ccy': '',
            'cbalsgn': '',
            'cbaltyp': '',
            'cbaldte': '',
            'cbal': '',
            'abalsgn': '',
            'abaldte': '',
            'abal': ''
        }

        csv_file = csv.reader(afile)
        trn = 0  # Used to numerate TRNs if none present in file.
        lst_line = None

        for line in csv_file:
            zline = ''  # Line that will be written to the MT9 file.
            # Ignore the header
            if line and line[-2].upper().replace(' ', '') == 'REF4(MT940ONLY)' or line[0] == '':
                continue
            # Invalid column count should raise an error.
            elif len(line) != 27:
                raise Exception('Bad column count %s : %s' % (str(line.count(',')), str(line)))

            line = convert_values(line, dtf)

            # Check to see whether a previous page should be closed.
            if (prev_line['stmtpg'] != line[4] or prev_line['account'] != line[2]) and prev_line['account'] != '':
                # Close the page: ":62F:D151015EUR1618033889"
                zline = ':62%s:%s%s%s%s\n' % (prev_line['cbaltyp'],
                                              prev_line['cbalsgn'],
                                              prev_line['cbaldte'],
                                              prev_line['ccy'],
                                              prev_line['cbal'])

                if prev_line['abalsgn'] != '':
                    # Write available balance line: ":64:C151015EUR4238,05"
                    zline += ':64:%s%s%s%s\n' % (prev_line['abalsgn'],
                                                 prev_line['abaldte'],
                                                 prev_line['ccy'],
                                                 prev_line['abal'])

            # Check to see whether it's a new message.
            if prev_line['sendbic'] != line[0].upper() or prev_line['recvbic'] != line[1].upper():
                if prev_line['sendbic'] != '':  # Close the last message
                    # Try and get the checksum of the message, and if successful add the CHK field and reset the file.
                    if chk:
                        zline += '-}{5:{CHK:%s}}\n' % chk
                    else:
                        zline += '-}{5:}\n'
                # Open the next message
                # Create Basic Header
                zline += '{1:%s%s%s%s%s}' % (appid,
                                             servid,
                                             line[0].ljust(12, 'X'),
                                             session_no,
                                             seqno)

                # Create Application Header
                if drctn == 'I':  # Inward (From Swift)
                    zline += '{2:I%s%s%s%s%s}' % (msg_type,
                                                  line[1].ljust(12, 'X'),
                                                  msg_prty,
                                                  dlvt_mnty,
                                                  obs)
                else:  # Outward (To Swift)
                    if mir is True:
                        # Auto generate mir
                        mir = (str(datetime.datetime.today()).replace('-', '')[2:8] +
                               line[0].ljust(12, 'X') +
                               session_no +
                               seqno)
                    # Add the block
                    zline += '{2:O%s%s%s%s%s%s}' % (msg_type,
                                                    inp_time,
                                                    mir,
                                                    out_date,
                                                    out_time,
                                                    msg_prty)
                # Create field 113 if present
                f113_ = '' if f113 is False else '{113:%s}' % str(f113).rjust(4, '0')
                zline += '{3:%s{118:%s}{4:\n' % (f113, mur)

            # Check to see whether a new page should be opened.
            if prev_line['stmtpg'] != line[4] or prev_line['account'] != line[2]:
                # Add the TRN
                if line[26] == '' or line[26].isspace():
                    zline += ':20:MT94050GEN%s\n' % str(trn).rjust(6, '0')
                    trn += 1
                else:
                    zline += ':20:%s\n' % line[26]
                # Add the Account number and Statement/Page numbers
                zline += ':25:%s\n:28C:%s/%s\n' % (line[2],
                                                   line[3].rjust(5, '0'),
                                                   line[4].rjust(5, '0'))
                # Add the opening balance
                zline += ':60%s:%s%s%s%s\n' % (line[6],
                                               line[5],
                                               line[7],
                                               line[24],
                                               line[8])
            # Now add the item line.
            zline += ':61:%s%s%s%s%s%s//%s\n' % (line[9],
                                                 line[10],
                                                 line[11],
                                                 line[12],
                                                 line[13],
                                                 line[14],
                                                 line[15])

            if line[16] and not line[16].isspace():
                zline += '%s\n' % line[16]
            if msg_type == '940' and line[25] and not line[25].isspace():
                # Add Ref4 for valid 940 items
                zline += ':86:%s\n' % line[25]

            zfile.write(zline)

            prev_line['account'] = line[2]
            prev_line['sendbic'] = line[0]
            prev_line['recvbic'] = line[1]
            prev_line['stmtno'] = line[3]
            prev_line['stmtpg'] = line[4]
            prev_line['ccy'] = line[24]
            prev_line['cbalsgn'] = line[17]
            prev_line['cbaltyp'] = line[18]
            prev_line['cbaldte'] = line[19]
            prev_line['cbal'] = line[20]
            prev_line['abalsgn'] = line[21]
            prev_line['abaldte'] = line[22]
            prev_line['abal'] = line[23]
            lst_line = line
        # Close the last line.
        zline = ':62F:%s%s%s%s\n' % (lst_line[17],
                                     lst_line[19],
                                     lst_line[24],
                                     lst_line[20])

        if lst_line[21] != '':
            # Write available balance line: ":64:C151015EUR4238,05"
            zline += ':64:%s%s%s%s\n' % (lst_line[21],
                                         lst_line[22],
                                         lst_line[24],
                                         lst_line[23])
        if chk:
            zline += '-}{5:{CHK:%s}}' % chk
        else:
            zline += '-}{5:}'

        zfile.write(zline)

    print('MT%s created successfully.' % msg_type)



def convert_values(xline, dtf):
    '''
    Converts supplied values to swift MT equivalents.
    '''
    for i, item in enumerate(xline):
        if i in [5, 6, 11, 17, 18, 21]:
            # Upper case Types and Signs.
            xline[i] = item.upper()
        elif i in [8, 12, 20, 23]:
            # All amounts, remove thousands seps, and replace decimal spot with comma
            xline[i] = item.replace(',', '').replace('.', ',').replace('-', '')
        # Convert dates to YYMMDD or MMDD
        elif i in [7, 9, 10, 19, 22]:
            if dtf == 'DDMMYYYY':
                xline[i] = item[8:10] + item[3:5] + item[:2] if i != 10 else item[3:5] + item[:2]
            elif dtf == 'MMDDYYYY':
                xline[i] = item[8:10] + item[:2] + item[3:5] if i != 10 else item[:2] + item[3:5]
            else:
                xline[i] = item[2:4] + item[5:7] + item[8:10] if i != 10 else item[5:7] + item[8:10]
        else:
            continue

    return (xline)


gen_mt9()
